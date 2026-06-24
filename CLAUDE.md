# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Router is an HTTP reverse proxy that listens on a single port and forwards requests to backend targets using round-robin load balancing. It can optionally persist request/response pairs as pretty-printed JSON files.

## Build & Run Commands

```bash
# Install/sync dependencies
uv sync

# Run the router (with config file)
uv run python -m ai_router -c config.yaml

# Run with CLI only (no config file)
uv run python -m ai_router -p 8080 -t localhost:9001 -t localhost:9002

# Run with config + CLI overrides
uv run python -m ai_router -c config.yaml -H 127.0.0.1 --listen-port 9999 --storage-enabled
```

There is no test suite or linter configured yet.

## Architecture

```
src/ai_router/
├── __init__.py      # Public API re-exports
├── __main__.py      # Entry point: CLI parse → config load/merge → uvicorn.run()
├── cli.py           # argparse definition, produces flat override dict
├── config.py        # Pydantic v2 models (ServerConfig, TargetConfig, StorageConfig, AppConfig)
├── forwarder.py     # Round-robin target selection + httpx-based forwarding
├── storage.py       # JSON file persistence with count gating and body formatting
└── app.py           # Starlette app factory with catch-all route
```

### Data Flow

1. `__main__.py` parses CLI args, loads YAML config via `AppConfig.from_yaml()`, merges CLI overrides via `AppConfig.merge_cli()`
2. `app.create_app()` instantiates a `Forwarder` (holds target list + round-robin logic) and a `StorageManager` (holds count + file writing)
3. A single Starlette `Route("/{path:path}")` catches all methods/paths → `catch_all` endpoint
4. The endpoint calls `forwarder.forward_with_target_info()` which selects the next target (round-robin when >1, direct when =1), forwards via httpx, and returns `(Response, target, request_data, response_data)`
5. `storage.store()` is called with the captured data; if enabled and under max_count, it writes `{id:06d}.json` with indent=4, ensure_ascii=False

### Key Patterns

- **Config merge**: Defaults → YAML → CLI. CLI always wins. Overrides use dotted-path keys (e.g. `server.listen_host`, `server.listen_port`).
- **Round-robin**: `itertools.cycle` over target indices, guarded by `asyncio.Lock` for async safety. When exactly 1 target is configured, the lock is bypassed.
- **Body formatting in storage**: `StorageManager._format_body()` checks Content-Type for `application/json` — if found, parses the body into a Python object so it serialises as nested JSON; otherwise stores as a plain string.
- **Hop-by-hop header filtering**: `Forwarder._filter_headers()` strips headers like `host`, `connection`, `transfer-encoding` before forwarding.
- **Non-blocking I/O**: Storage writes use `run_in_executor` to avoid blocking the event loop.

### Extension Points

- **New load-balancing strategies**: Extend `Forwarder` with a pluggable strategy class (currently hardcoded round-robin in `_next_index()`).
- **Additional storage backends**: Replace or wrap `StorageManager` — the interface is `store(request_data, response_data) -> int | None`.
- **Health checks**: Add a background task in `app.py`'s startup event that periodically probes targets and removes unhealthy ones from the forwarder.
