from datetime import UTC, datetime

from fastapi import FastAPI

APP_VERSION = "0.1.0-alpha"

app = FastAPI(
    title="BRAVO Script Monitor API",
    version=APP_VERSION,
    description="Central API for BRAVO Script Monitor.",
)


@app.get("/api/v1/live", tags=["system"])
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/ready", tags=["system"])
def ready() -> dict[str, str]:
    # Database and Redis checks will be added in Backend Foundation.
    return {"status": "ready"}


@app.get("/api/v1/version", tags=["system"])
def version() -> dict[str, str]:
    return {
        "component": "bsm-backend",
        "version": APP_VERSION,
        "api_version": "v1",
        "timestamp": datetime.now(UTC).isoformat(),
    }
