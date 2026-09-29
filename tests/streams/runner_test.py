"""Tests for Quix Streams application assembly."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from obsforge.config import Config
from obsforge.streams import runner
from obsforge.streams.models import StreamPipelineConfig
from obsforge.streams.runner import StreamSettingsError


class RecordingFactory:
    """Record keyword arguments and return them as a simple value."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return kwargs


class FakeStream:
    def __init__(self) -> None:
        self.transform: Any = None
        self.sink_value: Any = None

    def apply(self, transform: Any) -> FakeStream:
        self.transform = transform
        return self

    def sink(self, sink: Any) -> None:
        self.sink_value = sink


class FakeApplication:
    def __init__(self, **kwargs: Any) -> None:
        self.init_kwargs = kwargs
        self.topic_args: tuple[str, dict[str, Any]] | None = None
        self.stream = FakeStream()

    def topic(self, name: str, **kwargs: Any) -> object:
        self.topic_args = (name, kwargs)
        return object()

    def dataframe(self, topic: object) -> FakeStream:
        return self.stream


class ApplicationFactory:
    def __init__(self) -> None:
        self.application: FakeApplication | None = None

    def __call__(self, **kwargs: Any) -> FakeApplication:
        self.application = FakeApplication(**kwargs)
        return self.application


@pytest.fixture
def stream_settings(monkeypatch: pytest.MonkeyPatch) -> Config:
    monkeypatch.setenv(
        "OBSFORGE_DATABASE_URL",
        "postgresql://obsforge@db.example.com/obsdb",
    )
    monkeypatch.setenv("OBSFORGE_DATABASE_PASSWORD", "db-password")
    monkeypatch.setenv(
        "OBSFORGE_KAFKA_BROKER_ADDRESS", "kafka.example.com:9093"
    )
    monkeypatch.setenv("OBSFORGE_KAFKA_USERNAME", "kafka-user")
    monkeypatch.setenv("OBSFORGE_KAFKA_PASSWORD", "kafka-password")
    monkeypatch.setenv("OBSFORGE_KAFKA_SASL_MECHANISM", "PLAIN")
    monkeypatch.setenv(
        "OBSFORGE_SCHEMA_REGISTRY_URL", "https://registry.example.com"
    )
    monkeypatch.setenv("OBSFORGE_SCHEMA_REGISTRY_TOKEN", "registry-token")
    return Config()


@pytest.fixture
def pipeline() -> StreamPipelineConfig:
    return StreamPipelineConfig.model_validate(
        {
            "version": 1,
            "name": "scheduler-state",
            "consumer_group": "obsforge-scheduler-state-v1",
            "source": {"topic": "lsst.sal.Scheduler.observatoryState"},
            "sink": {
                "schema": "scheduler",
                "table": "observatory_state",
            },
            "transformations": [
                {
                    "operation": "drop_fields",
                    "fields": ["salIndex"],
                    "prefixes": ["private_"],
                },
                {
                    "operation": "epoch_seconds_to_datetime",
                    "field": "timestamp",
                    "input_scale": "tai",
                },
            ],
        }
    )


def test_build_application(
    monkeypatch: pytest.MonkeyPatch,
    stream_settings: Config,
    pipeline: StreamPipelineConfig,
) -> None:
    application_factory = ApplicationFactory()
    connection_factory = RecordingFactory()
    registry_factory = RecordingFactory()
    deserializer_factory = RecordingFactory()
    sink_factory = RecordingFactory()
    monkeypatch.setattr(runner, "Application", application_factory)
    monkeypatch.setattr(runner, "ConnectionConfig", connection_factory)
    monkeypatch.setattr(
        runner, "TokenSchemaRegistryClientConfig", registry_factory
    )
    monkeypatch.setattr(runner, "AvroDeserializer", deserializer_factory)
    monkeypatch.setattr(runner, "PostgreSQLSink", sink_factory)

    application = runner.build_application(stream_settings, pipeline)

    assert (
        application.init_kwargs["consumer_group"]
        == "obsforge-scheduler-state-v1"
    )
    assert application.init_kwargs["auto_create_topics"] is False
    assert connection_factory.calls == [
        {
            "bootstrap_servers": "kafka.example.com:9093",
            "security_protocol": "sasl_ssl",
            "sasl_mechanism": "SCRAM-SHA-512",
            "sasl_username": "kafka-user",
            "sasl_password": stream_settings.kafka_password,
        }
    ]
    assert registry_factory.calls == [
        {
            "url": "https://registry.example.com/",
            "bearer_auth_token": stream_settings.schema_registry_token,
        }
    ]
    assert application.topic_args is not None
    assert application.topic_args[0] == "lsst.sal.Scheduler.observatoryState"
    assert application.stream.transform(
        {
            "salIndex": 1,
            "timestamp": 1767225637.0,
            "tracking": True,
            "private_seqNum": 42,
        }
    ) == {
        "timestamp": datetime(2026, 1, 1, tzinfo=UTC),
        "tracking": True,
    }
    assert sink_factory.calls == [
        {
            "host": stream_settings.database_url.host,
            "port": stream_settings.database_url.port or 5432,
            "dbname": "obsdb",
            "user": "obsforge",
            "password": "db-password",
            "schema_name": "scheduler",
            "table_name": "observatory_state",
            "schema_auto_update": False,
            "include_metadata": False,
            "on_conflict_do_nothing": True,
        }
    ]
    assert application.stream.sink_value == sink_factory.calls[0]


def test_missing_runtime_settings(
    monkeypatch: pytest.MonkeyPatch,
    pipeline: StreamPipelineConfig,
) -> None:
    monkeypatch.setenv(
        "OBSFORGE_DATABASE_URL", "postgresql://obsforge@localhost/obsdb"
    )
    monkeypatch.delenv("OBSFORGE_KAFKA_BROKER_ADDRESS", raising=False)
    monkeypatch.delenv("OBSFORGE_KAFKA_USERNAME", raising=False)
    monkeypatch.delenv("OBSFORGE_KAFKA_PASSWORD", raising=False)
    monkeypatch.delenv("OBSFORGE_SCHEMA_REGISTRY_URL", raising=False)
    monkeypatch.delenv("OBSFORGE_SCHEMA_REGISTRY_TOKEN", raising=False)
    settings = Config()

    with pytest.raises(StreamSettingsError, match="KAFKA_BROKER_ADDRESS"):
        runner.build_application(settings, pipeline)


def test_schema_registry_token_config(stream_settings: Config) -> None:
    assert stream_settings.schema_registry_token is not None
    registry = runner.TokenSchemaRegistryClientConfig(
        url=str(stream_settings.schema_registry_url),
        bearer_auth_token=stream_settings.schema_registry_token,
    )

    assert registry.as_dict(plaintext_secrets=True) == {
        "url": "https://registry.example.com/",
        "bearer.auth.credentials.source": "STATIC_TOKEN",
        "bearer.auth.token": "registry-token",
        "bearer.auth.logical.cluster": "",
        "bearer.auth.identity.pool.id": "",
    }


def test_unmanaged_sink_target(
    stream_settings: Config, pipeline: StreamPipelineConfig
) -> None:
    pipeline.sink.table_name = "unmanaged_table"

    with pytest.raises(StreamSettingsError, match="not managed"):
        runner.build_application(stream_settings, pipeline)


def test_default_pipeline_path(stream_settings: Config) -> None:
    assert stream_settings.stream_config_path == Path(
        "/app/config/streams/scheduler-observatory-state.yaml"
    )
