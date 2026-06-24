"""Command-line argument parsing for the AI Router.

Parses CLI flags and produces a dictionary of overrides that can be
merged into the YAML-based configuration.
"""

from __future__ import annotations

import argparse
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the AI Router.

    Returns:
        An ArgumentParser instance with all CLI flags configured.
    """
    parser = argparse.ArgumentParser(
        prog="ai-router",
        description="HTTP reverse proxy with round-robin load balancing and optional request/response storage.",
    )

    # --- Config file ---
    parser.add_argument(
        "-c", "--config",
        type=str,
        default=None,
        help="Path to YAML configuration file.",
    )

    # --- Server overrides ---
    server_group = parser.add_argument_group("Server options")
    server_group.add_argument(
        "-H", "--host", "--listen-host",
        type=str,
        default=None,
        dest="listen_host",
        help="Host address to bind the listening socket (overrides config).",
    )
    server_group.add_argument(
        "-p", "--listen-port",
        type=int,
        default=None,
        help="Port to listen for incoming requests (overrides config).",
    )

    # --- Target overrides ---
    target_group = parser.add_argument_group("Target options")
    target_group.add_argument(
        "-t", "--target",
        type=str,
        action="append",
        default=None,
        dest="targets",
        metavar="HOST:PORT",
        help="Backend target in host:port format. Repeatable. "
             "When provided, replaces the target list from the config file.",
    )

    # --- Storage overrides ---
    storage_group = parser.add_argument_group("Storage options")
    storage_enabled = storage_group.add_mutually_exclusive_group()
    storage_enabled.add_argument(
        "--storage-enabled",
        action="store_true",
        default=None,
        dest="storage_enabled",
        help="Enable request/response storage.",
    )
    storage_enabled.add_argument(
        "--no-storage",
        action="store_false",
        default=None,
        dest="storage_enabled",
        help="Disable request/response storage.",
    )
    storage_group.add_argument(
        "--storage-path",
        type=str,
        default=None,
        help="Directory path for stored JSON files (overrides config).",
    )
    storage_group.add_argument(
        "--storage-max-count",
        type=int,
        default=None,
        help="Maximum number of request/response pairs to store (overrides config).",
    )

    return parser


def cli_overrides_to_dict(args: argparse.Namespace) -> dict[str, Any]:
    """Convert parsed CLI arguments into a flat override dictionary.

    Only non-None values are included, keyed by their dotted config path
    (e.g. ``server.listen_port``).

    Args:
        args: Parsed argument namespace from ``build_parser().parse_args()``.

    Returns:
        A dict suitable for passing to ``AppConfig.merge_cli()``.
    """
    overrides: dict[str, Any] = {}

    if args.listen_host is not None:
        overrides["server.listen_host"] = args.listen_host
    if args.listen_port is not None:
        overrides["server.listen_port"] = args.listen_port

    if args.targets is not None:
        targets = []
        for t in args.targets:
            if ":" not in t:
                raise ValueError(f"Invalid target format: '{t}'. Expected 'host:port'.")
            host, port_str = t.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                raise ValueError(f"Invalid port in target: '{t}'. Port must be an integer.")
            targets.append({"host": host, "port": port})
        overrides["targets"] = targets

    if args.storage_enabled is not None:
        overrides["storage.enabled"] = args.storage_enabled
    if args.storage_path is not None:
        overrides["storage.path"] = args.storage_path
    if args.storage_max_count is not None:
        overrides["storage.max_count"] = args.storage_max_count

    return overrides
