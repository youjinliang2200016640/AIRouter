"""Request/response storage as JSON files.

Persists forwarded request/response pairs to disk as indented JSON files.
Supports count-based gating and automatic JSON body pretty-printing.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_router.config import StorageConfig


class StorageManager:
    """Manages persistent storage of request/response pairs as JSON files.

    Each pair is written as ``{count:06d}.json`` inside the configured
    storage directory.  JSON bodies are detected by Content-Type and
    pretty-printed before writing.
    """

    def __init__(self, config: StorageConfig) -> None:
        """Initialise the storage manager.

        Args:
            config: Storage configuration (enabled, path, max_count).
        """
        self._config = config
        self._count: int = 0
        self._lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        """Whether storage is currently enabled."""
        return self._config.enabled

    @property
    def count(self) -> int:
        """Number of pairs stored so far (monotonic, never resets)."""
        return self._count

    async def store(
        self,
        request_data: dict[str, Any],
        response_data: dict[str, Any],
    ) -> int | None:
        """Persist a request/response pair if storage is enabled and within limits.

        Args:
            request_data: Dict with keys ``method``, ``url``, ``headers``, ``body``.
            response_data: Dict with keys ``status_code``, ``headers``, ``body``.

        Returns:
            The assigned record ID (1-based), or ``None`` if storage is disabled
            or the max_count limit has been reached.
        """
        if not self._config.enabled:
            return None

        async with self._lock:
            if self._count >= self._config.max_count:
                return None
            self._count += 1
            record_id = self._count

        record = self._build_record(record_id, request_data, response_data)
        await self._write_record(record_id, record)
        return record_id

    def _build_record(
        self,
        record_id: int,
        request_data: dict[str, Any],
        response_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Build the full storage record for a request/response pair.

        Args:
            record_id: Monotonic record identifier.
            request_data: Raw request metadata and body.
            response_data: Raw response metadata and body.

        Returns:
            A dict ready for JSON serialisation.
        """
        req_headers = request_data.get("headers", {})
        resp_headers = response_data.get("headers", {})

        return {
            "id": record_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request": {
                "method": request_data.get("method", "UNKNOWN"),
                "url": request_data.get("url", ""),
                "headers": req_headers,
                "body": self._format_body(
                    request_data.get("body", b""),
                    req_headers.get("content-type", ""),
                ),
            },
            "response": {
                "status_code": response_data.get("status_code", 0),
                "headers": resp_headers,
                "body": self._format_body(
                    response_data.get("body", b""),
                    resp_headers.get("content-type", ""),
                ),
            },
        }

    @staticmethod
    def _format_body(body: bytes, content_type: str) -> Any:
        """Format a body for storage.

        If the Content-Type indicates JSON, the body is parsed and returned
        as a structured object so it will be pretty-printed by the JSON encoder.
        Otherwise the body is decoded as UTF-8 text (or returned as-is on failure).

        Args:
            body: Raw body bytes.
            content_type: Lowercased Content-Type header value.

        Returns:
            Either a parsed JSON object, a decoded string, or the raw bytes
            as a fallback string.
        """
        if not body:
            return ""

        if "application/json" in content_type:
            try:
                return json.loads(body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Body claims to be JSON but isn't valid — store as text.
                return _safe_decode(body)

        return _safe_decode(body)

    async def _write_record(self, record_id: int, record: dict[str, Any]) -> None:
        """Write a single record to disk as an indented JSON file.

        Args:
            record_id: Record ID used for the filename.
            record: The record dict to serialise.
        """
        storage_path = Path(self._config.path)
        storage_path.mkdir(parents=True, exist_ok=True)

        filename = storage_path / f"{record_id:06d}.json"
        json_bytes = json.dumps(
            record,
            indent=4,
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")

        # Use run_in_executor to avoid blocking the event loop on disk I/O.
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _write_bytes, filename, json_bytes)


def _safe_decode(data: bytes) -> str:
    """Decode bytes to string, falling back to repr on failure."""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def _write_bytes(path: Path, data: bytes) -> None:
    """Synchronous file write helper (runs in executor)."""
    with open(path, "wb") as f:
        f.write(data)
