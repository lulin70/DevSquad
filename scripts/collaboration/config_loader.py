#!/usr/bin/env python3
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATHS = [
    Path.home() / ".devsquad.yaml",
    Path.home() / ".devsquad" / "config.yaml",
    Path(".devsquad.yaml"),
    Path("devsquad.yaml"),
]


@dataclass
class DevSquadConfig:
    backend: str = "mock"
    base_url: str | None = None
    model: str | None = None
    timeout: int = 120
    max_roles: int = 10
    max_task_length: int = 10000
    min_task_length: int = 5
    strict_validation: bool = False
    output_format: str = "structured"
    checkpoint_enabled: bool = True
    checkpoint_dir: str = "./checkpoints"
    workflow_enabled: bool = False
    workflow_dir: str = "./workflows"
    cache_enabled: bool = True
    cache_dir: str = "./data/llm_cache"
    log_level: str = "WARNING"

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "base_url": self.base_url,
            "model": self.model,
            "timeout": self.timeout,
            "max_roles": self.max_roles,
            "max_task_length": self.max_task_length,
            "min_task_length": self.min_task_length,
            "strict_validation": self.strict_validation,
            "output_format": self.output_format,
            "checkpoint_enabled": self.checkpoint_enabled,
            "checkpoint_dir": self.checkpoint_dir,
            "workflow_enabled": self.workflow_enabled,
            "workflow_dir": self.workflow_dir,
            "cache_enabled": self.cache_enabled,
            "cache_dir": self.cache_dir,
            "log_level": self.log_level,
        }


class ConfigManager:
    """
    Configuration manager for DevSquad.

    Loads config from (in order of priority):
    1. Environment variables (highest)
    2. ~/.devsquad.yaml or ./devsquad.yaml
    3. Built-in defaults (lowest)
    """

    ENV_MAP = {
        "DEVSQUAD_LLM_BACKEND": "backend",
        "DEVSQUAD_BACKEND": "backend",
        "DEVSQUAD_BASE_URL": "base_url",
        "DEVSQUAD_MODEL": "model",
        "DEVSQUAD_TIMEOUT": ("timeout", int),
        "DEVSQUAD_MAX_ROLES": ("max_roles", int),
        "DEVSQUAD_OUTPUT_FORMAT": "output_format",
        "DEVSQUAD_STRICT": ("strict_validation", lambda v: v.lower() in ("true", "1", "yes")),
        "DEVSQUAD_STRICT_VALIDATION": ("strict_validation", lambda v: v.lower() in ("true", "1", "yes")),
        "DEVSQUAD_LOG_LEVEL": "log_level",
        "DEVSQUAD_CHECKPOINT_DIR": "checkpoint_dir",
        "DEVSQUAD_CACHE_DIR": "cache_dir",
        "DEVSQUAD_CHECKPOINT_ENABLED": ("checkpoint_enabled", lambda v: v.lower() in ("true", "1", "yes")),
        "DEVSQUAD_CACHE_ENABLED": ("cache_enabled", lambda v: v.lower() in ("true", "1", "yes")),
    }

    def __init__(self, config_path: str | None = None):
        self.config = DevSquadConfig()
        self._config_path = None

        if config_path:
            self._config_path = Path(config_path)
        else:
            for path in DEFAULT_CONFIG_PATHS:
                if path.exists():
                    self._config_path = path
                    break

        self._load()

    def _load(self):
        if self._config_path and self._config_path.exists():
            self._load_from_file(self._config_path)

        self._load_from_env()

    def _load_from_file(self, path: Path):
        try:
            if yaml is None:
                logger.warning("pyyaml not installed, skipping config file %s", path)
                return
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            devsquad_data = data.get("devsquad", data)

            for key, value in devsquad_data.items():
                key_mapped = key.replace("-", "_")
                if hasattr(self.config, key_mapped):
                    current = getattr(self.config, key_mapped)
                    if isinstance(current, bool) and not isinstance(value, bool):
                        value = str(value).lower() in ("true", "1", "yes")
                    elif isinstance(current, int) and not isinstance(value, int):
                        try:
                            value = int(value)
                        except (ValueError, TypeError):
                            logger.warning("Invalid int value for %s: %s", key, value)
                            continue
                    elif isinstance(current, float) and not isinstance(value, (int, float)):
                        try:
                            value = float(value)
                        except (ValueError, TypeError):
                            logger.warning("Invalid float value for %s: %s", key, value)
                            continue
                    setattr(self.config, key_mapped, value)

            logger.info("Config loaded from %s", path)
        except Exception as e:
            logger.warning("Failed to load config from %s: %s", path, e)

    def _load_from_env(self):
        for env_key, mapping in self.ENV_MAP.items():
            env_value = os.environ.get(env_key)
            if env_value is None:
                continue

            if isinstance(mapping, tuple):
                attr_name, converter = mapping
                try:
                    setattr(self.config, attr_name, converter(env_value))
                except (ValueError, TypeError):
                    logger.warning("Invalid env value for %s: %s", env_key, env_value)
            else:
                setattr(self.config, mapping, env_value)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self.config, key, default)

    def set(self, key: str, value: Any):
        if hasattr(self.config, key):
            setattr(self.config, key, value)
        else:
            logger.warning("Unknown config key: %s", key)

    def save(self, path: str | None = None):
        save_path = Path(path) if path else (self._config_path or Path.home() / ".devsquad.yaml")
        save_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if yaml is None:
                logger.warning("pyyaml not installed, cannot save config to %s", save_path)
                return
            data = {"devsquad": self.config.to_dict()}
            with open(save_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            logger.info("Config saved to %s", save_path)
        except Exception as e:
            logger.warning("Failed to save config: %s", e)

    @property
    def config_path(self) -> str | None:
        return str(self._config_path) if self._config_path else None

    def to_dict(self) -> dict[str, Any]:
        return self.config.to_dict()
