"""Tests for arq queue storage diagnostics."""

from typing import Any, cast

import pytest
from structlog.testing import capture_logs

from obsforge.config import config
from obsforge.storage import EnrichmentQueueStore


class FakeArqJob:
    id = "arq-1"


class FakeArqStatus:
    value = "queued"


class FakeArqMetadata:
    status = FakeArqStatus()


class FakeArqResult:
    success = True


class FakeArqQueue:
    async def enqueue(
        self, task_name: str, job_id: int, *, _queue_name: str
    ) -> FakeArqJob:
        return FakeArqJob()

    async def abort_job(
        self, arq_job_id: str, *, queue_name: str, timeout: int
    ) -> bool:
        return True

    async def get_job_metadata(
        self, arq_job_id: str, *, queue_name: str
    ) -> FakeArqMetadata:
        return FakeArqMetadata()

    async def get_job_result(
        self, arq_job_id: str, *, queue_name: str
    ) -> FakeArqResult:
        return FakeArqResult()


@pytest.mark.asyncio
async def test_queue_store_debug_logs_arq_operations() -> None:
    queue = FakeArqQueue()
    store = EnrichmentQueueStore(cast("Any", queue))

    with capture_logs() as logs:
        arq_job_id = await store.enqueue(1)
        aborted = await store.abort(arq_job_id)
        status = await store.status(arq_job_id)
        succeeded = await store.succeeded(arq_job_id)

    assert arq_job_id == "arq-1"
    assert aborted is True
    assert status == "queued"
    assert succeeded is True
    assert [log["event"] for log in logs] == [
        "Enqueueing enrichment job in arq",
        "Enqueued enrichment job in arq",
        "Aborting enrichment job in arq",
        "Aborted enrichment job in arq",
        "Checking enrichment job arq status",
        "Checked enrichment job arq status",
        "Checking enrichment job arq result",
        "Checked enrichment job arq result",
    ]
    for log in logs:
        assert log["log_level"] == "debug"
        assert log["arq_queue_name"] == config.arq_queue_name
    assert logs[0]["enrichment_job_id"] == 1
    assert logs[0]["arq_task_name"] == "run_enrichment"
    assert logs[1]["arq_job_id"] == "arq-1"
    assert logs[3]["arq_aborted"] is True
    assert logs[5]["arq_status"] == "queued"
    assert logs[7]["arq_success"] is True
