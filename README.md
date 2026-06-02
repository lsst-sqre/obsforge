# obsforge

ObsForge: The RSP observation metadata enrichment service
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

Stop the services when done:

```sh
docker compose down
```

To discard local Postgres data and start over, also remove the Compose volume:

```sh
docker compose down --volumes
```

The Compose stack is for interactive local development. The tox test harness
is managed separately and should keep owning its own test services.
