"""Configuration models for the AI Router.

Defines the full configuration schema using Pydantic v2, including
YAML file loading and CLI argument merging.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    """Server listen configuration."""

    listen_host: str = Field(default="0.0.0.0", description="Host address to bind the listening socket")
    listen_port: int = Field(default=8080, ge=1, le=65535, description="Port to listen for incoming requests")


class TargetConfig(BaseModel):
    """A single backend target."""

    host: str = Field(description="Target hostname or IP address")
    port: int = Field(ge=1, le=65535, description="Target port number")


class StorageConfig(BaseModel):
    """Storage configuration for persisting request/response pairs."""

    enabled: bool = Field(default=False, description="Enable request/response storage")
    path: str = Field(default="./storage", description="Directory path for stored JSON files")
    max_count: int = Field(default=1000, ge=1, description="Maximum number of request/response pairs to store")


class AppConfig(BaseModel):
    """Top-level application configuration."""

    server: ServerConfig = Field(default_factory=ServerConfig)
    targets: list[TargetConfig] = Field(default_factory=list, description="List of backend targets")
    storage: StorageConfig = Field(default_factory=StorageConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> AppConfig:
        """Load configuration from a YAML file.

        Args:
            path: Path to the YAML configuration file.

        Returns:
            An AppConfig instance populated from the file.

        Raises:
            FileNotFoundError: If the config file does not exist.
            ValueError: If the YAML is malformed or validation fails.
        """
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}

        return cls.model_validate(raw)

    def merge_cli(self, cli_overrides: dict[str, Any]) -> AppConfig:
        """Merge CLI overrides into this configuration.

        CLI values take precedence over existing (YAML-provided) values.
        Returns a *new* AppConfig instance; does not mutate self.

        Args:
            cli_overrides: Dictionary of CLI-provided overrides keyed by
                           dotted path (e.g. ``server.listen_port``, ``storage.enabled``).

        Returns:
            A new AppConfig with CLI values applied on top.
        """
        data = self.model_dump()

        for key_path, value in cli_overrides.items():
            if value is None:
                continue
            self._set_nested(data, key_path, value)

        return AppConfig.model_validate(data)

    @staticmethod
    def _set_nested(data: dict[str, Any], key_path: str, value: Any) -> None:
        """Set a value in a nested dict using a dotted key path.

        Example: ``_set_nested(data, "server.listen_port", 9999)``
        """
        keys = key_path.split(".")
        current = data
        for key in keys[:-1]:
            current = current.setdefault(key, {})
        current[keys[-1]] = value
