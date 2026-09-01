"""Quix Streams application assembly and execution."""

from pathlib import Path
from typing import Any, Literal, cast

from pydantic import SecretStr
from quixstreams import Application
from quixstreams.kafka.configuration import ConnectionConfig
from quixstreams.models import SchemaRegistryClientConfig
from quixstreams.models.serializers.avro import AvroDeserializer
from quixstreams.sinks.community.postgresql import PostgreSQLSink

from ..config import Config
from ..schema import SchemaBase
from .models import StreamPipelineConfig, load_stream_pipeline_config
from .transforms import apply_transformations

__all__ = ["StreamSettingsError", "build_application", "run_stream"]


class StreamSettingsError(ValueError):
    """Raised when required runtime stream settings are missing."""


class TokenSchemaRegistryClientConfig(SchemaRegistryClientConfig):
    """Schema Registry configuration using a static bearer token."""

    bearer_auth_credentials_source: Literal["STATIC_TOKEN"] = "STATIC_TOKEN"
    bearer_auth_token: SecretStr
    # The Confluent client requires these fields for static tokens. Empty
    # values preserve standard bearer-token behavior for Sasquatch.
    bearer_auth_logical_cluster: str = ""
    bearer_auth_identity_pool_id: str = ""


def _secret_value(secret: SecretStr | None) -> str | None:
    return secret.get_secret_value() if secret else None


def _validate_settings(config: Config) -> None:
    required = {
        "OBSFORGE_KAFKA_BROKER_ADDRESS": config.kafka_broker_address,
        "OBSFORGE_KAFKA_USERNAME": config.kafka_username,
        "OBSFORGE_KAFKA_PASSWORD": config.kafka_password,
        "OBSFORGE_SCHEMA_REGISTRY_URL": config.schema_registry_url,
        "OBSFORGE_SCHEMA_REGISTRY_TOKEN": config.schema_registry_token,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise StreamSettingsError(
            "Missing required stream settings: " + ", ".join(missing)
        )


def _validate_sink_target(pipeline: StreamPipelineConfig) -> None:
    table_key = pipeline.sink.table_name
    if pipeline.sink.schema_name != "public":
        table_key = f"{pipeline.sink.schema_name}.{table_key}"
    if table_key not in SchemaBase.metadata.tables:
        raise StreamSettingsError(
            f"Sink target {table_key!r} is not managed by ObsForge metadata"
        )


def build_application(
    config: Config,
    pipeline: StreamPipelineConfig,
) -> Any:
    """Build a Quix application from runtime secrets and pipeline config."""
    _validate_settings(config)
    _validate_sink_target(pipeline)
    kafka_broker_address = cast("str", config.kafka_broker_address)
    kafka_password = cast("SecretStr", config.kafka_password)
    schema_registry_url = str(config.schema_registry_url)
    schema_registry_token = cast("SecretStr", config.schema_registry_token)

    kafka_connection = ConnectionConfig(
        bootstrap_servers=kafka_broker_address,
        security_protocol=config.kafka_security_protocol,
        sasl_mechanism="SCRAM-SHA-512",
        sasl_username=config.kafka_username,
        sasl_password=kafka_password,
    )
    app = Application(
        broker_address=kafka_connection,
        consumer_group=pipeline.consumer_group,
        auto_create_topics=False,
    )

    registry = TokenSchemaRegistryClientConfig(
        url=schema_registry_url,
        bearer_auth_token=schema_registry_token,
    )
    source = app.topic(
        pipeline.source.topic,
        value_deserializer=AvroDeserializer(
            schema_registry_client_config=registry
        ),
    )
    stream = app.dataframe(source)
    stream = stream.apply(
        lambda value: apply_transformations(value, pipeline.transformations)
    )

    database_url = config.database_url
    database_user = database_url.username
    database_name = database_url.path.lstrip("/") if database_url.path else ""
    if not database_url.host or not database_user or not database_name:
        raise StreamSettingsError(
            "OBSFORGE_DATABASE_URL must include host, user, and database name"
        )
    database_password = _secret_value(config.database_password)
    if database_password is None:
        database_password = database_url.password or ""

    sink = PostgreSQLSink(
        host=database_url.host,
        port=database_url.port or 5432,
        dbname=database_name,
        user=database_user,
        password=database_password,
        schema_name=pipeline.sink.schema_name,
        table_name=pipeline.sink.table_name,
        schema_auto_update=False,
        include_metadata=False,
        on_conflict_do_nothing=True,
    )
    stream.sink(sink)
    return app


def run_stream(config: Config, pipeline_path: Path) -> None:
    """Load, build, and run one configured stream until interrupted."""
    pipeline = load_stream_pipeline_config(pipeline_path)
    application = build_application(config, pipeline)
    application.run()
