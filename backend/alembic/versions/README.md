# Alembic revisions

Revision files are generated from `backend/` with:

```bash
alembic revision --autogenerate -m "describe schema change"
alembic upgrade head
```

Generated migrations must be reviewed before commit. Production deployments run migrations as an explicit release step, not automatically during API startup.
