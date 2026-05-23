"""Tests for the ObsForge command-line interface."""

from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from obsforge.cli import main
from obsforge.schema import SchemaBase


class FakeEngine:
    """Small async-engine test double."""

    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


def test_help() -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["help"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "Administrative command-line interface" in result.output


def test_init(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    engine = FakeEngine()
    calls: list[tuple[str, Any]] = []
    alembic_config_path = tmp_path / "alembic.ini"

    def fake_create_database_engine(url: Any, password: Any) -> FakeEngine:
        calls.append(("create_database_engine", str(url)))
        return engine

    async def fake_initialize_database(
        engine: FakeEngine, logger: Any, *, schema: Any, reset: bool
    ) -> None:
        calls.append(("initialize_database", reset))
        assert schema is SchemaBase.metadata

    def fake_stamp_database(path: Path) -> None:
        calls.append(("stamp_database", path))

    monkeypatch.setattr(
        "obsforge.cli.create_database_engine", fake_create_database_engine
    )
    monkeypatch.setattr(
        "obsforge.cli.initialize_database", fake_initialize_database
    )
    monkeypatch.setattr("obsforge.cli.stamp_database", fake_stamp_database)
    runner = CliRunner()

    result = runner.invoke(
        main,
        [
            "init",
            "--alembic-config-path",
            str(alembic_config_path),
            "--reset",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert engine.disposed is True
    assert calls == [
        ("create_database_engine", "postgresql://obsforge@localhost/obsforge"),
        ("initialize_database", True),
        ("stamp_database", alembic_config_path),
    ]


def test_update_schema(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[list[str], bool, str]] = []
    alembic_config_path = tmp_path / "alembic.ini"

    def fake_run(args: list[str], *, check: bool, cwd: str) -> None:
        calls.append((args, check, cwd))

    monkeypatch.setattr("obsforge.cli.subprocess.run", fake_run)
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["update-schema", "--alembic-config-path", str(alembic_config_path)],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert calls == [(["alembic", "upgrade", "head"], True, str(tmp_path))]


def test_validate_schema_current(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    engine = FakeEngine()
    calls: list[tuple[str, Any]] = []
    alembic_config_path = tmp_path / "alembic.ini"

    def fake_create_database_engine(url: Any, password: Any) -> FakeEngine:
        calls.append(("create_database_engine", str(url)))
        return engine

    async def fake_is_database_current(
        engine: FakeEngine, logger: Any, path: Path
    ) -> bool:
        calls.append(("is_database_current", path))
        return True

    monkeypatch.setattr(
        "obsforge.cli.create_database_engine", fake_create_database_engine
    )
    monkeypatch.setattr(
        "obsforge.cli.is_database_current", fake_is_database_current
    )
    runner = CliRunner()

    result = runner.invoke(
        main,
        [
            "validate-schema",
            "--alembic-config-path",
            str(alembic_config_path),
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert engine.disposed is True
    assert calls == [
        ("create_database_engine", "postgresql://obsforge@localhost/obsforge"),
        ("is_database_current", alembic_config_path),
    ]


def test_validate_schema_out_of_date(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    engine = FakeEngine()

    def fake_create_database_engine(url: Any, password: Any) -> FakeEngine:
        return engine

    async def fake_is_database_current(
        engine: FakeEngine, logger: Any, path: Path
    ) -> bool:
        return False

    monkeypatch.setattr(
        "obsforge.cli.create_database_engine", fake_create_database_engine
    )
    monkeypatch.setattr(
        "obsforge.cli.is_database_current", fake_is_database_current
    )
    runner = CliRunner()

    result = runner.invoke(
        main,
        [
            "validate-schema",
            "--alembic-config-path",
            str(tmp_path / "alembic.ini"),
        ],
    )

    assert result.exit_code == 1
    assert "Database schema is not current" in result.output
    assert engine.disposed is True
