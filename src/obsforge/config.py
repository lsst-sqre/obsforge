"""Configuration definition."""

from pathlib import Path
from typing import cast

from arq.connections import RedisSettings
from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from safir.arq import ArqMode, build_arq_redis_settings
from safir.logging import LogLevel, Profile, configure_logging
from safir.pydantic import EnvAsyncPostgresDsn, EnvRedisDsn

__all__ = ["Config", "config"]


class Config(BaseSettings):
    """Configuration for obsforge."""

    model_config = SettingsConfigDict(
        env_prefix="OBSFORGE_", case_sensitive=False
    )

    database_url: EnvAsyncPostgresDsn = Field(
        ...,
        title="PostgreSQL DSN",
        description="DSN of PostgreSQL database for ObsForge durable state",
    )

    database_password: SecretStr | None = Field(
        None, title="Password for ObsForge database"
    )

    arq_mode: ArqMode = Field(
        ArqMode.production, title="Mode for the arq queue dependency"
    )

    arq_queue_url: EnvRedisDsn = Field(
        cast("EnvRedisDsn", "redis://localhost:6379/0"),
        title="Redis DSN",
        description="DSN of Redis storage for the arq queue",
    )

    arq_queue_password: SecretStr | None = Field(
        None, title="Password for the arq Redis queue"
    )

    arq_queue_name: str = Field(
        "arq:queue", title="Name of the arq queue used by ObsForge"
    )

    enrichment_max_tries: int = Field(
        5,
        title="Maximum arq attempts for an enrichment job",
        ge=1,
    )

    butler_label: str = Field(
        "prompt",
        title="Butler repository label",
        description="Label used by the worker to create Prompt Butler clients",
    )

    butler_repository: HttpUrl | Path | None = Field(
        None,
        title="Butler repository",
        description=(
            "Prompt Butler repository path or URL for worker enrichment"
        ),
    )

    obscore_config: HttpUrl | Path | None = Field(
        None,
        title="ObsCore exporter configuration",
        description="Path or URL to the lsst.dax.obscore prompt.yaml config",
    )

    obscore_dataset_type: str = Field(
        "preliminary_visit_image",
        title="ObsCore dataset type",
        description="Dataset type selected from the ObsCore exporter config",
    )

    log_level: LogLevel = Field(
        LogLevel.INFO, title="Log level of the application's logger"
    )

    log_profile: Profile = Field(
        Profile.development, title="Application logging profile"
    )

    name: str = Field("obsforge", title="Name of application")

    path_prefix: str = Field("/obsforge", title="URL prefix for application")

    slack_webhook: SecretStr | None = Field(
        None,
        title="Slack webhook for alerts",
        description="If set, alerts will be posted to this Slack webhook",
    )

    @property
    def arq_redis_settings(self) -> RedisSettings:
        """Create Redis settings for arq."""
        return build_arq_redis_settings(
            self.arq_queue_url, self.arq_queue_password
        )


config = Config()
"""Configuration for obsforge."""

configure_logging(
    profile=config.log_profile,
    log_level=config.log_level,
    name="obsforge",
)
