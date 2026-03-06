# Phase 3 Test Suite

This folder contains the first end-to-end testing structure for Phase 3.

## Layers

- `unit/`: deterministic tests for isolated components (engine contracts, converter contracts).
- `integration/`: in-process pipeline tests combining loader/converter/engine/tool registry behavior.
- `worker/`: Celery task execution tests with patched dependencies and database side-effect assertions.

## Principles

- No network calls.
- No real LLM calls.
- No real Redis dependency in tests.
- Multi-tenant boundaries validated through test data and inputs.
- Keep tests deterministic and fast.

## Expansion Roadmap

- Add router integration tests for `/api/agent-platform/*`.
- Add failure-path worker tests (retry branch and max-retries behavior).
- Add tenant isolation tests for every service and pipeline stage.
- Add full E2E tests with ephemeral Postgres + Redis in CI.
