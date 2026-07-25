import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.api import APP_VERSION, router
from app.settings import settings

logger = logging.getLogger("bsm.api")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger.info("Starting BRAVO Script Monitor API version %s", APP_VERSION)
    yield
    logger.info("Stopping BRAVO Script Monitor API")


def create_app() -> FastAPI:
    application = FastAPI(
        title="BRAVO Script Monitor API",
        version=APP_VERSION,
        description="Central API for BRAVO Script Monitor.",
        lifespan=lifespan,
        openapi_tags=[
            {"name": "system", "description": "Service health and version information."},
            {"name": "organizations", "description": "Organization management."},
            {"name": "installations", "description": "Installation management."},
        ],
    )
    application.add_middleware(RequestIdMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    @application.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.exception("Unhandled API exception request_id=%s", request_id, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "code": "internal_server_error",
                "message": "An unexpected error occurred",
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id} if request_id else None,
        )

    application.include_router(router)
    return application


app = create_app()
