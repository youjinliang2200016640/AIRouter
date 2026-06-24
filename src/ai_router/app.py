"""Starlette application factory for the AI Router.

Creates a Starlette app with a catch-all route that forwards every
incoming request to backend targets and optionally persists the
request/response pair.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from ai_router.config import AppConfig
from ai_router.forwarder import Forwarder
from ai_router.storage import StorageManager

logger = logging.getLogger(__name__)


def create_app(config: AppConfig) -> Starlette:
    """Build a Starlette application from the given configuration.

    Args:
        config: Fully-resolved application configuration.

    Returns:
        A Starlette ASGI application ready to be served by uvicorn.
    """
    forwarder = Forwarder(config.targets)
    storage = StorageManager(config.storage)

    logger.info(
        "Router initialised: listen=%s:%d, targets=%d, storage=%s",
        config.server.listen_host,
        config.server.listen_port,
        forwarder.target_count,
        "enabled" if storage.enabled else "disabled",
    )

    async def catch_all(request: Request) -> Response:
        """Catch-all endpoint that forwards every request to a backend target.

        Forwards the request via the round-robin forwarder and, if storage
        is enabled, persists the request/response pair as a JSON file.
        """
        response, target, req_data, resp_data = await forwarder.forward_with_target_info(request)

        stored_id = await storage.store(req_data, resp_data)
        if stored_id is not None:
            logger.debug(
                "Stored record #%d: %s %s -> %s:%d (%d)",
                stored_id,
                req_data["method"],
                req_data["url"],
                target.host,
                target.port,
                resp_data["status_code"],
            )

        return response

    @asynccontextmanager
    async def lifespan(app: Starlette):
        """Application lifespan: log startup/shutdown events."""
        logger.info("AI Router started successfully.")
        yield
        logger.info("AI Router shutting down. Total records stored: %d.", storage.count)

    # Register a single catch-all route for all common HTTP methods.
    # The {path:path} converter captures the full URL path including slashes.
    routes = [
        Route(
            "/{path:path}",
            endpoint=catch_all,
            methods=[
                "GET", "POST", "PUT", "DELETE", "PATCH",
                "HEAD", "OPTIONS",
            ],
        ),
    ]

    return Starlette(routes=routes, lifespan=lifespan)
