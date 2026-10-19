"""Tests for ObsForge configuration."""

from pathlib import Path

import pytest
from pydantic import HttpUrl, SecretStr, ValidationError

from obsforge.config import Config


def test_worker_path_settings_resolve_from_raw_env_strings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test worker path settings resolve as paths from environment values."""
    monkeypatch.setenv(
        "OBSFORGE_DATABASE_URL", "postgresql://obsforge@localhost/obsdb"
    )
    monkeypatch.setenv("OBSFORGE_BUTLER_REPOSITORY", "/repo/prompt")
    monkeypatch.setenv("OBSFORGE_BUTLER_ACCESS_TOKEN", "worker-token")
    monkeypatch.setenv("OBSFORGE_OBSCORE_CONFIG", "/configs/prompt.yaml")

    settings = Config()

    assert settings.butler_repository == Path("/repo/prompt")
    assert settings.obscore_config == Path("/configs/prompt.yaml")
    assert isinstance(settings.butler_access_token, SecretStr)
    assert settings.butler_access_token.get_secret_value() == "worker-token"


def test_worker_url_settings_resolve_from_raw_env_strings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test worker URL settings resolve as URLs from environment values."""
    monkeypatch.setenv(
        "OBSFORGE_DATABASE_URL", "postgresql://obsforge@localhost/obsdb"
    )
    monkeypatch.setenv(
        "OBSFORGE_BUTLER_REPOSITORY", "https://data.example.com/repo"
    )
    monkeypatch.setenv(
        "OBSFORGE_OBSCORE_CONFIG",
        "https://data.example.com/configs/prompt.yaml",
    )

    settings = Config()

    assert isinstance(settings.butler_repository, HttpUrl)
    assert str(settings.butler_repository) == "https://data.example.com/repo"
    assert isinstance(settings.obscore_config, HttpUrl)
    assert (
        str(settings.obscore_config)
        == "https://data.example.com/configs/prompt.yaml"
    )


def test_stream_authentication_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test stream tokens are secret and Kafka requires a SASL transport."""
    monkeypatch.setenv(
        "OBSFORGE_DATABASE_URL", "postgresql://obsforge@localhost/obsdb"
    )
    monkeypatch.setenv("OBSFORGE_SCHEMA_REGISTRY_TOKEN", "registry-token")

    settings = Config()

    assert isinstance(settings.schema_registry_token, SecretStr)
    assert settings.schema_registry_token.get_secret_value() == (
        "registry-token"
    )

    monkeypatch.setenv("OBSFORGE_KAFKA_SECURITY_PROTOCOL", "plaintext")
    with pytest.raises(ValidationError):
        Config()
