"""Entry point for the AI Router.

Parses CLI arguments, loads/merges configuration, and starts the
uvicorn server.
"""

from __future__ import annotations

import logging
import sys

import uvicorn

from ai_router.cli import build_parser, cli_overrides_to_dict
from ai_router.config import AppConfig


def main() -> None:
    """Main entry point: parse args, load config, start server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("ai_router")

    parser = build_parser()
    args = parser.parse_args()

    # Load configuration: YAML file first, then CLI overrides
    if args.config:
        try:
            config = AppConfig.from_yaml(args.config)
            logger.info("Loaded configuration from %s", args.config)
        except FileNotFoundError:
            logger.error("Configuration file not found: %s", args.config)
            sys.exit(1)
        except Exception as exc:
            logger.error("Failed to parse configuration file: %s", exc)
            sys.exit(1)
    else:
        logger.info("No config file specified; using defaults.")
        config = AppConfig()

    # Merge CLI overrides (CLI always wins)
    overrides = cli_overrides_to_dict(args)
    if overrides:
        config = config.merge_cli(overrides)
        logger.info("Applied %d CLI override(s).", len(overrides))

    # Validate that we have at least one target
    if not config.targets:
        logger.error(
            "No backend targets configured. "
            "Provide targets via config file or -t/--target flag."
        )
        sys.exit(1)

    logger.info(
        "Starting AI Router on %s:%d with %d target(s).",
        config.server.listen_host,
        config.server.listen_port,
        len(config.targets),
    )
    for i, t in enumerate(config.targets):
        logger.info("  Target %d: %s:%d", i + 1, t.host, t.port)

    if config.storage.enabled:
        logger.info(
            "Storage enabled: path=%s, max_count=%d",
            config.storage.path,
            config.storage.max_count,
        )

    # Import here so config is fully resolved before app creation
    from ai_router.app import create_app  # noqa: E402

    app = create_app(config)

    uvicorn.run(
        app,
        host=config.server.listen_host,
        port=config.server.listen_port,
        log_config=None,  # Use our own logging config
        access_log=True,
    )


if __name__ == "__main__":
    main()
