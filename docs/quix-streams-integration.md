# Quix Streams integration

Run Quix Streams pipelines from the same container
image as the API and arq worker. Each process consumes one Kafka
topic, applies transformations defined in a YAML file, and writes
the results to one pre-existing ObsDB table with the Quix Streams PostgreSQL sink.

Keep the three contracts separate:

| Concern | Authority | Behavior |
| --- | --- | --- |
| Source/wire schema | Sasquatch Schema Registry | Quix fetches the writer schema by schema ID while deserializing Avro. ObsForge does not copy the Avro schema. |
| Target relational schema | ObsForge SQLAlchemy and Alembic | Models and migrations create target schemas and tables. Quix schema auto-update is disabled. |
| Routing and transformations | Versioned ObsForge YAML | A pipeline selects its topic, consumer group, target table, and ordered transformations. Secrets remain in environment settings. |

This follows ObsForge's existing database ownership model while avoiding a
second, potentially stale copy of each source schema.

## Implemented first pipeline

The initial pipeline is:

```text
lsst.sal.Scheduler.observatoryState
        |
        | SASL/SCRAM-SHA-512
        v
Quix AvroDeserializer -----> Sasquatch Schema Registry
        |                     Authorization: Bearer <token>
        | drop_fields(fields=["salIndex"], prefixes=["private_"])
        | epoch_seconds_to_datetime(field="timestamp", input_scale="tai")
        v
Quix PostgreSQLSink
        |
        | INSERT; no table CREATE/ALTER
        v
scheduler.observatory_state in ObsDB
```

The YAML defines the pipeline:

```yaml
version: 1
name: scheduler-observatory-state
consumer_group: obsforge-scheduler-observatory-state-v1

source:
  topic: lsst.sal.Scheduler.observatoryState

sink:
  schema: scheduler
  table: observatory_state

transformations:
  - operation: drop_fields
    fields:
      - salIndex
    prefixes:
      - private_
  - operation: epoch_seconds_to_datetime
    field: timestamp
    input_scale: tai
```

Version 1 accepts `drop_fields` and `epoch_seconds_to_datetime`. `drop_fields`
supports explicit field names and prefixes. The explicit selector removes
`salIndex`; the prefix selector automatically excludes any new `private_*`
fields introduced upstream. `epoch_seconds_to_datetime` converts numeric TAI
or UTC epoch seconds to a timezone-aware UTC `datetime` for PostgreSQL. The
Scheduler pipeline declares `input_scale: tai`; pipelines carrying Unix UTC
seconds use `input_scale: utc`.

The target table keeps the Kafka/Avro field spelling, including camel case, so
the sink can insert dictionaries without a rename layer. SQLAlchemy attributes
use Python snake case while mapping to those physical column names. The
converted `timestamp` is stored as PostgreSQL `timestamptz` and is the table's
primary key. Its primary-key index replaces the previous separate timestamp
index.

Quix uses `schema_auto_update=False`, making Alembic the only table DDL writer.
It also uses `include_metadata=False`; otherwise the sink injects a Kafka
record timestamp column named `timestamp`, colliding with the Scheduler payload
field. Topic auto-creation is disabled, and the runner refuses a YAML sink
target absent from ObsForge SQLAlchemy metadata. The sink uses `ON CONFLICT DO
NOTHING`, making reprocessing idempotent when the same timestamp is replayed.

One connector caveat remains: Quix 3.25 issues
`CREATE SCHEMA IF NOT EXISTS` during sink setup even when schema auto-update is
disabled. Alembic creates the schema first, but the statement may still affect
the privileges required by a future insert-only database role. Resolve that
upstream or in a narrowly tested sink adapter before separating migration and
writer roles.

Pipeline YAML should be treated as application code and versioned alongside the SQLAlchemy models and Alembic migrations.
The YAML contains contract-level decisions:
- Target schema and table
- Fields retained or dropped
- Source topic/schema binding
- Consumer-group identity, whose changes can cause replay

Recommended ownership model:

- Keep pipeline YAML files under config/streams/ in the ObsForge repository.
- Copy them into the container image.
- Select the desired packaged pipeline through the deployment command or environment variable.
- Keep credentials, broker addresses, registry URLs, database URLs, replica counts, and resource limits in Kubernetes configuration.
- Deploy Alembic migrations before deploying the corresponding image.

A ConfigMap can still be used as a delivery mechanism if it is generated from the same version-controlled pipeline file and released atomically with the matching image. It should not be independently hand-edited.


## Runtime and deployment

Apply Alembic migrations before starting a stream process. For local
development, run the commands through `uv` and provide the repository-local
configuration paths:

```sh
uv run obsforge update-schema \
  --alembic-config-path alembic.ini
uv run obsforge process-stream \
  --stream-config-path config/streams/scheduler-observatory-state.yaml
```

Inside the runtime container, the virtual environment is already on `PATH`,
and the CLI defaults to `/app/alembic.ini` and
`/app/config/streams/scheduler-observatory-state.yaml`:

```sh
obsforge update-schema
obsforge process-stream
```

Required runtime settings are:

```sh
export OBSFORGE_KAFKA_BROKER_ADDRESS=kafka.example:9093
export OBSFORGE_KAFKA_USERNAME=obsforge
export OBSFORGE_KAFKA_PASSWORD=...
export OBSFORGE_SCHEMA_REGISTRY_URL=https://schema-registry.example
export OBSFORGE_SCHEMA_REGISTRY_TOKEN=...
```

The existing `OBSFORGE_DATABASE_URL` and `OBSFORGE_DATABASE_PASSWORD` select
ObsDB. Kafka authentication is fixed to `SCRAM-SHA-512`; the transport defaults
to `SASL_SSL` and can be changed to `SASL_PLAINTEXT` with
`OBSFORGE_KAFKA_SECURITY_PROTOCOL` for a trusted deployment.

Schema Registry access uses the required token as an HTTP bearer token. Quix
3.25 does not expose static bearer-token fields on its registry settings model,
although its pinned Confluent client supports them. ObsForge therefore extends
the Quix model with those fields. The token remains a `SecretStr` until Quix
builds the client configuration.

Quix Streams 3.25 pins `confluent-kafka` below 2.12. On Python 3.14,
`confluent-kafka` 2.11.1 may compile from source because a platform wheel is
unavailable. The container builds the matching, checksummed librdkafka 2.11.1
and copies its runtime library into the final image. Local development systems
must likewise provide librdkafka 2.11.1 or newer headers and libraries.

## Multiple topics and scaling

Use one pipeline process per topic by default. Give each pipeline a stable,
pipeline-specific consumer group. Replicas of the same pipeline share that
group and can scale up to the source topic's partition count; unrelated
pipelines use different groups and can be deployed, restarted, and scaled
independently.

For the first several topics, keep one YAML file per pipeline and run the same
container image once for each selected file. A later configuration catalog may
list multiple pipelines, but the CLI should normally select and run only one
entry per process.

Quix supports multiple DataFrames in one `Application`, but they share one
consumer loop and checkpoint lifecycle. Sink flushes are sequential, so a slow
PostgreSQL sink or failing topic can delay or replay work for every topic in
that application. Bundle topics only when they are low-volume, operationally
homogeneous, and allowed to share a failure domain.

Each PostgreSQL sink instance owns a connection. Budget stream connections as
the sum of pipeline replicas and sink instances, in addition to API and worker
database pools. PostgreSQL insert capacity is likely to become the limiting
resource before Kafka when telemetry volume grows.

## Schema evolution and failure policy

The initial policy is deliberately strict:

- New `private_*` source fields are dropped and require no database change;
  explicitly configured fields such as `salIndex` are also dropped.
- A new retained field makes PostgreSQL reject the insert until an ObsForge
  model and Alembic migration add the target column.
- Removed required fields or incompatible type changes also fail at the sink.
- Deploy schema migrations before code or configuration that emits new fields.

This favors visible pipeline failure over silent table mutation. Stream
deployments should alert on process restarts, consumer lag, deserialization
errors, PostgreSQL write errors, batch latency, and database connections.

The community PostgreSQL sink provides at-least-once delivery. The timestamp
primary key and conflict-ignore behavior deduplicate a replay after a failure
between a PostgreSQL commit and a Kafka offset checkpoint. This assumes the
Scheduler emits at most one distinct observatory-state record for a timestamp;
a second record with the same timestamp is intentionally ignored. Pipelines
where timestamps are not unique must instead use source topic, partition, and
offset columns—or a stable domain event ID—as a primary or unique key.

The PostgreSQL sink is a Quix community connector. Load, failure-recovery, and
upgrade testing against ObsDB are required before treating this path as a
production service.

## Options considered

### Target schema ownership

1. **ObsForge SQLAlchemy and Alembic (recommended and implemented).** This
   provides reviewable DDL, predictable grants and indexes, and schema
   validation consistent with the existing service. The cost is a migration
   for every retained source field change.
2. **Quix sink schema auto-update.** This requires runtime DDL privileges and
   maps Python values to database types from observed records. It cannot safely
   express removals, renames, constraints, indexes, or semantic type choices.
3. **Generate SQLAlchemy and Alembic from Avro.** This may become useful after
   several manually modeled topics reveal stable conventions, but nullability,
   logical types, arrays, identifiers, indexes, and retention are not always
   mechanical mappings.

### Source schema management

1. **Resolve schemas from Schema Registry at runtime (recommended and
   implemented).** This preserves the Confluent schema ID embedded in every
   message and supports multiple compatible writer versions in one topic.
2. **Vendor Avro schemas in ObsForge.** This makes builds self-contained but
   duplicates the upstream authority. A local reader schema may later be useful
   for an intentional compatibility projection, but should not replace writer
   schema lookup.

### Transformation configuration

1. **Versioned, image-packaged YAML in ObsForge (recommended and
   implemented).** It is small, reviewable, validated, and released with
   compatible code and migrations. A generated ConfigMap is an acceptable
   GitOps transport only when it remains tied to the same release; it is not a
   separate source of truth.
2. **Helm values or environment variables only.** These are convenient for
   routing but awkward for ordered, typed transformation definitions.
3. **Database-managed dynamic configuration.** This enables runtime changes but
   requires an admin API, auditing, reload semantics, and coordination with
   schema migrations. It is unnecessary for the current iteration.

## Next iteration

Before adding production topics, add CI contract tests that load every pipeline
definition and validate its sink target against SQLAlchemy metadata. Also
validate representative schema versions against a non-production Sasquatch
topic, add consumer-lag and sink-error metrics, and choose an idempotency key.
Then create pipeline-specific YAML, SQLAlchemy models, and Alembic migrations
for each additional topic while keeping deployment and scaling independent.

References: [Quix Streams Schema Registry](https://quix.io/docs/quix-streams/advanced/schema-registry.html),
[Kafka authentication configuration](https://quix.io/docs/quix-streams/configuration.html),
[Quix PostgreSQL sink](https://quix.io/docs/quix-streams/connectors/sinks/postgresql-sink.html),
and the [Scheduler SAL interface](https://ts-xml.lsst.io/sal_interfaces/Scheduler.html).
