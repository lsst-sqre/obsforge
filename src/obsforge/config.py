"""Configuration definition."""

from typing import cast

from arq.connections import RedisSettings
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from safir.arq import ArqMode, build_arq_redis_settings
from safir.logging import LogLevel, Profile
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
