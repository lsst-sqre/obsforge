# AGENTS.md

This repository implements a Safir-style FastAPI application and follows the architectural patterns described in SQR-072.

## Core Architecture

- Follow layered application structure:
  `handlers -> services -> storage`
- Keep route handlers thin.
  Handlers should parse request inputs, obtain dependencies, call one service method, and translate the result into an HTTP response.
- Do not put business logic in handlers.
- Do not put business logic in FastAPI dependencies.
- Put business logic in service classes.
- Put translation to external systems in storage classes.
  Examples: SQL, Redis, external REST APIs, Kubernetes objects, or other service adapters.
- Services may call storage and other services, but handlers should not call storage directly.

## Dependency Injection

- Use FastAPI dependencies for shared resources, request preprocessing, and authentication/authorization checks.
- Use a `RequestContext` dependency when handlers need per-request state,
  auth-derived resources, shared clients, or other values that would otherwise
  be repeated across several handlers.
- Use a `Factory` to construct services from the request context and shared
  dependencies once the app has multiple services, non-trivial construction
  logic, or handler dependency lists that are becoming long.
  For very small features, creating a service directly from a dependency can be
  acceptable if it keeps the code simpler.
- Inject dependencies into service constructors.
  Do not construct clients or storage objects inside service methods unless there is a strong project-specific reason.
- Pass only the dependencies a service actually needs.
  Do not pass broad “context” or “container” objects into services or storage.

## Configuration

- Define application configuration in `config.py`.
- Use a single typed `Config` class based on `pydantic-settings`.
- Prefer `pathlib.Path` for filesystem paths.
- Prefer `datetime.timedelta` for durations.
- Keep configuration parsing centralized.

## Application Structure

- `main.py`: create and wire the FastAPI application, routers, middleware, logging, and exception handlers
- `config.py`: typed application configuration
- `factory.py`: construct services and their collaborators
- `exceptions.py`: application-specific exceptions
- `dependencies/`: FastAPI dependencies only
- `handlers/`: HTTP handlers only
- `services/`: business logic
- `storage/`: translation to persistence layers and external services
- `models/` or `models.py`: request, response, and internal models
- `templates/`: Jinja templates if the app returns templated content
- `tests/`: pytest test suite

## Models

- Use Pydantic models for request and response bodies.
- Use typed internal models or dataclasses for structured data passed between layers.
- Prefer models over loose dictionaries for data crossing module boundaries.
- Convert generic external data into internal models as early as practical.

## Handlers

- Prefer `Annotated[...]` for FastAPI parameters and dependencies.
- Start handler argument lists with `*` to force keyword-only parameters.
- Let FastAPI and Pydantic perform as much validation and serialization as possible.
- Keep handler code small enough that the route body is mostly orchestration.
- If an endpoint becomes complex, move logic into a service rather than adding helper logic inside the handler module.

## Services

- Service APIs should express actions in the domain.
  Examples: `create_job`, `get_dataset`, `delete_token`.
- Service method parameters should be minimal and explicit.
- Services should return models or simple typed values.
- Keep service logic independent of HTTP details whenever possible.

## Storage

- Storage classes are responsible for mechanical translation only.
- Add storage classes when a feature talks to persistence layers or external
  systems, such as SQL databases, Redis, object storage, Kubernetes APIs, or
  external REST APIs.
- Do not create a storage layer for pure domain logic that has no external
  system or persistence boundary.
- Storage should not make authorization decisions.
- Storage should not contain business rules.
- Storage may enforce invariants required by the backing system, such as referential integrity or protocol constraints.

## Exceptions

- Use custom exception classes for domain and request errors.
- Invalid client requests should use exceptions compatible with Safir/FastAPI error handling.
- Construct exceptions from typed inputs when useful so message formatting stays centralized.

## Safir Conventions

- Prefer Safir helpers for:
  logging,
  metadata endpoints,
  exception handling,
  middleware,
  auth integration,
  and related FastAPI infrastructure.
- Keep observability wiring in application bootstrap and dependencies, not in business logic.
- Use `logger_dependency` from `safir.dependencies.logger` for
  unauthenticated request handlers.
- Use `auth_logger_dependency` from `safir.dependencies.gafaelfawr` for routes
  protected by Gafaelfawr so log messages include the authenticated user.
- Bind useful domain context with `logger = logger.bind(...)` before passing a
  logger deeper into services.
- Use `structlog.get_logger(__name__)` or `config.logger_name` when logging
  outside request handlers.
- Test structured logs with `caplog` and
  `safir.testing.logging.parse_log_tuples`.

## Testing

- Use `pytest`.
- Use `tox` as the primary local test runner, matching the Safir template
  workflow.
- Run `tox run` to execute the default test steps.
- Run `tox run -e py` to run the pytest test suite.
- Run `tox list` to inspect the available tox environments.
- Run targeted checks with tox when appropriate:
  `tox run -e typing` for mypy, and `tox run -e lint` for linting and
  formatting.
- Run `tox run-parallel -p auto` when you want all default test steps in
  parallel.
- Put end-to-end route tests in `tests/handlers`.
- Put direct service tests in `tests/services`.
- Put shared fixtures in `tests/conftest.py`.
- Put shared mocks, fakes, and helpers in `tests/support`.
- Prefer testing behavior through the HTTP interface for normal flows.
- Add direct service tests for edge cases that are awkward to reach through HTTP.
- Keep tests explicit and readable rather than overly abstract.

## Coding Guidance For Agents

- Preserve layer boundaries when adding new features.
- When implementing a feature, update every affected layer together.
  Do not create empty or unnecessary layers solely to satisfy the architecture
  pattern; let the app grow into the structure when the feature needs it.
- If the app is still small, it is acceptable to keep models in `models.py`.
  Split into a `models/` package when that file becomes crowded or mixes unrelated domains.
- If a feature talks to an external system and the translation logic starts growing, introduce or expand a storage layer rather than adding more logic to a service.
- Prefer adding structure early over letting handlers accumulate special cases.

## Reference Style

- Use SQR-072 as the primary architectural reference.
- Use `datalinker` as a reference for:
  typed settings,
  request context dependencies,
  small factories,
  Safir-based application setup,
  and pytest organization.
- Do not copy simplifications from a reference app if they weaken the intended architecture for this project.
