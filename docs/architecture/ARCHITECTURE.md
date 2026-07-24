# BRAVO Script Monitor — Architecture Specification

**Version:** 0.1 Draft

## System context

```text
User / Operator
      |
      v
External Nginx Reverse Proxy (TLS)
      |
      v
BSM Backend API  <---->  PostgreSQL
      |
      +----------> Redis
      |
      v
BSM Agents on managed servers
```

## Components

### Backend API

FastAPI application exposing versioned REST endpoints. It owns authorization, validation, orchestration, audit creation, and persistence boundaries.

### PostgreSQL

System of record for identities, inventory, scripts, schedules, jobs, executions, events, and audit records.

### Redis

Ephemeral cache and queue coordination. PostgreSQL remains authoritative.

### BSM Agent

Outbound-only managed-node component. It enrolls, sends heartbeats, receives authorized jobs, executes scripts under policy, persists an offline queue, and submits results.

### Frontend

API-first web console. It must not bypass backend authorization or access databases directly.

## Trust boundaries

- TLS terminates at the controlled external reverse proxy.
- Agents authenticate independently using revocable credentials.
- Database and Redis are not publicly exposed.
- Script execution requires authorization, policy validation, and audit recording.

## Availability model for MVP

A single BSM application instance with persistent PostgreSQL storage. Components expose liveness and readiness endpoints. HA is deferred but contracts must not prevent it.

## Data principles

- UUID identifiers.
- UTC timestamps in storage.
- append-oriented events and audit records;
- explicit lifecycle states;
- idempotency for retried agent submissions;
- retention rules documented per data class.
