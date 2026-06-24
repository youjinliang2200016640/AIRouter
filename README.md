# AI Router

An HTTP reverse proxy router with round-robin load balancing and optional request/response JSON storage.

## Features

- **Reverse proxy**: Listens on a single port and forwards all HTTP requests to backend targets
- **Round-robin load balancing**: Distributes requests evenly across the backend pool (direct forward when only 1 target)
- **JSON storage**: Optionally persists request/response pairs as pretty-printed JSON files with configurable limits
- **YAML + CLI configuration**: Configure via a YAML file, with CLI flags to override any setting

## Quick Start

```bash
# Install dependencies
uv sync

# Run with example config (adjust targets first)
uv run ai-router -c config.example.yaml

# Run with CLI overrides only (no config file)
uv run ai-router -p 8080 -t localhost:9001 -t localhost:9002 --storage-enabled
```

## Configuration

### YAML File

```yaml
server:
  listen_host: "0.0.0.0"
  listen_port: 8080

targets:
  - host: "localhost"
    port: 9001

storage:
  enabled: false
  path: "./storage"
  max_count: 1000
```

### CLI Flags

| Flag | Description |
|---|---|
| `-c, --config PATH` | Path to YAML config file |
| `-H, --host, --listen-host HOST` | Override listen host |
| `-p, --listen-port PORT` | Override listen port |
| `-t, --target HOST:PORT` | Add target (repeatable, replaces config targets) |
| `--storage-enabled` / `--no-storage` | Enable/disable storage |
| `--storage-path PATH` | Override storage directory |
| `--storage-max-count N` | Override max stored records |

CLI flags always take precedence over YAML values.

## Storage Format

Each stored pair is written as `{id}.json` in the storage directory:

```json
{
    "id": 1,
    "timestamp": "2026-06-24T12:00:00.000000",
    "request": {
        "method": "POST",
        "url": "http://localhost:8080/api/chat",
        "headers": {"content-type": "application/json"},
        "body": {
            "prompt": "hello"
        }
    },
    "response": {
        "status_code": 200,
        "headers": {"content-type": "application/json"},
        "body": {
            "reply": "hi there"
        }
    }
}
```

JSON bodies are automatically detected by Content-Type and pretty-printed (indent=4, ensure_ascii=False).

## Development

```bash
# Install dependencies
uv sync

# Run the router
uv run python -m ai_router -c config.yaml

# Run with inline targets (no config file needed)
uv run python -m ai_router -p 8080 -t localhost:9001
```

## License

MIT
