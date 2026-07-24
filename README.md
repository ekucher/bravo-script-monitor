# BRAVO Script Monitor

BRAVO Script Monitor (BSM) — централізована платформа BRAVOSOFT для моніторингу, автоматизації, аудиту та керування службовими сценаріями й агентами.

> Поточна версія: `0.1.0-alpha`  
> Статус: Sprint 0 — Foundation

## Архітектура MVP

```text
BSM Agent -> HTTPS REST API -> FastAPI -> PostgreSQL
                                  |
                                  +-> Redis
                                  |
                                  +-> Web Console
```

TLS завершується на зовнішньому Nginx reverse proxy. PostgreSQL і Redis не публікуються назовні.

## Швидкий запуск середовища розробки

```bash
cp .env.example .env
docker compose up --build -d
curl http://localhost:8080/api/v1/live
curl http://localhost:8080/api/v1/version
```

Swagger UI після запуску доступний за адресою `http://localhost:8080/docs`.

## Структура

- `backend/` — FastAPI backend;
- `frontend/` — web console;
- `agent/windows/` — PowerShell 7 agent;
- `database/` — міграції та SQL assets;
- `docs/` — PRS, архітектура, API, agent, security, deployment, ADR і RFC;
- `.github/` — CI та шаблони GitHub.

## Документація

- [Project Constitution](CONSTITUTION.md)
- [Roadmap](ROADMAP.md)
- [Product Requirements](docs/product/PRS.md)
- [Architecture Specification](docs/architecture/ARCHITECTURE.md)
- [ADR-0001: Technology foundation](docs/adr/ADR-0001-technology-foundation.md)

## Ліцензія

Ліцензійна модель буде остаточно затверджена до першого публічного релізу.
