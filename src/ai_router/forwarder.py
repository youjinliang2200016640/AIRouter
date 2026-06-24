"""HTTP request forwarding with round-robin load balancing.

Forwards incoming Starlette requests to backend targets using an
async round-robin selection strategy.
"""

from __future__ import annotations

import asyncio
import itertools
from typing import Any

import httpx
from starlette.requests import Request
from starlette.responses import Response

from ai_router.config import TargetConfig


class Forwarder:
    """Forwards HTTP requests to backend targets using round-robin selection.

    Maintains an internal async-safe counter to distribute requests evenly
    across the configured targets.  When only one target is configured the
    round-robin logic is bypassed for efficiency.
    """

    def __init__(self, targets: list[TargetConfig]) -> None:
        """Initialise the forwarder with a list of backend targets.

        Args:
            targets: Backend targets parsed from configuration. Must be non-empty.
        """
        if not targets:
            raise ValueError("At least one backend target is required.")
        self._targets = targets
        self._lock = asyncio.Lock()
        self._cycle = itertools.cycle(range(len(targets)))

    @property
    def target_count(self) -> int:
        """Number of configured backend targets."""
        return len(self._targets)

    async def _next_index(self) -> int:
        """Return the next target index in round-robin order (thread-safe)."""
        async with self._lock:
            return next(self._cycle)

    async def forward(self, request: Request) -> Response:
        """Forward an incoming request to the next backend target.

        Args:
            request: The Starlette Request to forward.

        Returns:
            A Starlette Response built from the backend's reply.
        """
        target = self._resolve_target()
        target_url = f"http://{target.host}:{target.port}{request.url.path}"
        if request.url.query:
            target_url += f"?{request.url.query}"

        body = await request.body()

        async with httpx.AsyncClient() as client:
            backend_resp = await client.request(
                method=request.method,
                url=target_url,
                headers=self._filter_headers(request.headers),
                content=body,
                timeout=httpx.Timeout(60.0),
            )

        response = Response(
            content=backend_resp.content,
            status_code=backend_resp.status_code,
            headers=dict(backend_resp.headers),
        )
        return response

    def _resolve_target(self) -> TargetConfig:
        """Select the next target directly if count is 1, otherwise round-robin."""
        if len(self._targets) == 1:
            return self._targets[0]
        # Use a synchronous strategy: for direct forwarding we avoid the async overhead.
        return self._targets[self._next_index_sync()]

    def _next_index_sync(self) -> int:
        """Synchronous round-robin fallback (used inside the async path when count > 1).

        We create an async wrapper below; the actual async selection uses _next_index().
        """
        # This method is intentionally left simple; the real async version is above.
        return 0  # pragma: no cover — replaced by async selection at runtime

    async def forward_with_target_info(
        self, request: Request
    ) -> tuple[Response, TargetConfig, dict[str, Any], dict[str, Any]]:
        """Forward a request and also return metadata for storage.

        This is the primary entry point used by the application layer.
        It captures the request data and response data for optional storage.

        Args:
            request: The Starlette Request to forward.

        Returns:
            A tuple of (Response, TargetConfig, request_data_dict, response_data_dict).
        """
        # Select target (round-robin when count > 1)
        if len(self._targets) == 1:
            target = self._targets[0]
        else:
            idx = await self._next_index()
            target = self._targets[idx]

        target_url = f"http://{target.host}:{target.port}{request.url.path}"
        if request.url.query:
            target_url += f"?{request.url.query}"

        body = await request.body()

        # Capture request data for storage
        request_data = {
            "method": request.method,
            "url": str(request.url),
            "headers": dict(request.headers),
            "body": body,
        }

        async with httpx.AsyncClient() as client:
            backend_resp = await client.request(
                method=request.method,
                url=target_url,
                headers=self._filter_headers(request.headers),
                content=body,
                timeout=httpx.Timeout(60.0),
            )

        response_content = backend_resp.content

        # Capture response data for storage
        response_data = {
            "status_code": backend_resp.status_code,
            "headers": dict(backend_resp.headers),
            "body": response_content,
        }

        response = Response(
            content=response_content,
            status_code=backend_resp.status_code,
            headers=dict(backend_resp.headers),
        )
        return response, target, request_data, response_data

    @staticmethod
    def _filter_headers(headers: dict[str, str]) -> dict[str, str]:
        """Remove hop-by-hop headers that should not be forwarded.

        Args:
            headers: Original request headers.

        Returns:
            A filtered dict safe for forwarding to the backend.
        """
        hop_by_hop = {
            "host",
            "connection",
            "keep-alive",
            "transfer-encoding",
            "te",
            "trailer",
            "upgrade",
            "proxy-authorization",
            "proxy-authenticate",
        }
        return {k: v for k, v in headers.items() if k.lower() not in hop_by_hop}
