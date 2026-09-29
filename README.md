# obsforge

ObsForge: a metadata enrichment service for Rubin Observatory observations
Learn more at https://obsforge.lsst.io

obsforge is developed with [FastAPI](https://fastapi.tiangolo.com) and [Safir](https://safir.lsst.io).

## Local Postgres and Redis

ObsForge local development uses Docker Compose for stateful services only. Run
the FastAPI app and arq worker on the host so that reloads and debugging stay
simple.

Start Postgres and Redis from this directory:

```sh
docker compose up -d postgres redis
```

Configure the host shell that will run ObsForge:

```sh
export OBSFORGE_DATABASE_URL=postgresql://obsforge@localhost/obsdb
export OBSFORGE_DATABASE_PASSWORD=INSECURE-PASSWORD
export OBSFORGE_ARQ_MODE=production
export OBSFORGE_ARQ_QUEUE_URL=redis://localhost:6379/0
export OBSFORGE_ALEMBIC_CONFIG_PATH=./alembic.ini
```

The FastAPI app can register jobs with only Postgres and Redis configured. To
run the worker and populate ObsCore rows, also configure the Prompt Butler
repository and the ObsCore exporter config:

```sh
export OBSFORGE_BUTLER_LABEL=prompt
export OBSFORGE_BUTLER_REPOSITORY=/path/to/prompt/butler
export OBSFORGE_OBSCORE_CONFIG=/path/to/prompt.yaml
export OBSFORGE_OBSCORE_DATASET_TYPE=preliminary_visit_image
```

The worker uses a remote Butler and requires a service token:

```sh
export OBSFORGE_BUTLER_ACCESS_TOKEN=...
```

To enable debug-level application logs, also set:

```sh
export OBSFORGE_LOG_LEVEL=DEBUG
```

Initialize the database and start the development server:

```sh
uv run obsforge init --reset
uv run uvicorn obsforge.main:app --reload
```

When testing queued enrichment, start the arq worker in a second shell with
the same environment:

```sh
uv run arq obsforge.worker.main.WorkerSettings
```

Exercise the local API from another shell:

```sh
BASE=http://127.0.0.1:8000/obsforge

curl -sS "$BASE/" | jq .

PAYLOAD='{
  "instrument": "LSSTCam",
  "day_obs": 20260327,
  "visit": 20260327123456,
  "datasets": [
    {
      "dataset_type": "preliminary_visit_image",
      "id": "019ba0a6-0173-765f-bf27-56884ff9342a"
    }
  ],
  "timespan": {
    "begin": "2026-03-27T08:15:10Z",
    "end": "2026-03-27T08:15:45Z"
  }
}'

RESPONSE=$(
  curl -sS \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" \
    "$BASE/register"
)

echo "$RESPONSE" | jq .

JOB_ID=$(echo "$RESPONSE" | jq -r '.id')

curl -sS "$BASE/jobs/$JOB_ID" | jq .
```

The `datasets` entries are persisted in the job's `registration_payload`.
During enrichment, the worker selects entries whose `dataset_type` matches
`OBSFORGE_OBSCORE_DATASET_TYPE`, uses their UUIDs to constrain
`lsst.dax.obscore`, and upserts the returned ObsCore records into ObsDB.

Registering the same `instrument` and `visit` pair again is idempotent:

```sh
curl -sS \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  "$BASE/register" | jq .
```

To abort an enrichment job:

```sh
curl -i -sS -X DELETE "$BASE/jobs/$JOB_ID"
```

The abort command must run while the queued arq job still exists, otherwise it returns:

```sh
{"detail":"Queued job not found"}
```

## Quix streams integration

ObsForge can run Quix Streams pipelines defined as YAML files in
`config/streams/`. It consumes Avro messages from Kafka, applies
transformations, and writes the results to Alembic-managed PostgreSQL tables.
The pipeline YAML also declares its Kafka consumer group, allowing each topic
pipeline to scale independently while its replicas share a stable group.

Install ObsForge and configure the connections:

```sh
uv sync
export OBSFORGE_KAFKA_BROKER_ADDRESS=kafka.example:9093
export OBSFORGE_KAFKA_USERNAME=obsforge
export OBSFORGE_KAFKA_PASSWORD=...
export OBSFORGE_SCHEMA_REGISTRY_URL=https://schema-registry.example
export OBSFORGE_SCHEMA_REGISTRY_TOKEN=...
obsforge process-stream \
  --stream-config-path config/streams/scheduler-observatory-state.yaml
```

Run the stream as a separate long-lived process from the API and arq worker.
See the [Quix Streams integration](docs/quix-streams-integration.md)
for schema ownership, deployment, evolution, and delivery decisions.
