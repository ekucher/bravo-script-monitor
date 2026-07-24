# ADR-0001: Technology foundation

- **Status:** Accepted
- **Date:** 2026-07-25

## Context

BSM requires an API-first platform with strong schema validation, PostgreSQL support, generated API documentation, containerized deployment, and a Windows-native first agent.

## Decision

Use:

- Python 3.13 and FastAPI for the backend;
- PostgreSQL 17 as the system of record;
- SQLAlchemy 2 and Alembic for persistence and migrations;
- Redis for ephemeral cache and queue coordination;
- React, TypeScript, and Material UI for the web console;
- PowerShell 7 for the first Windows agent;
- Docker Compose for development and initial single-node deployment;
- external Nginx for TLS termination and reverse proxying;
- OpenAPI 3.1 as the API contract.

## Consequences

The project receives mature tooling and explicit contracts, but must control dependency upgrades, maintain asynchronous boundaries carefully, and prevent Redis from becoming an undocumented source of truth.
