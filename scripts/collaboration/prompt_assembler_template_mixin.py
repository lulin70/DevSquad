"""Template loading mixin for PromptAssembler.

Extracts YAML configuration loading (with module-level caching) and the
template variant / compression-override tables so the main assembler
file can focus on orchestration.

Responsibilities (from IMPROVEMENT_PLAN_V3.9.2.md P2-3):
    - Template reading & caching
    - Variant selection tables
    - Compression-aware overrides
"""

import logging
import os

from .prompt_assembler_base import PromptAssemblerBase, TaskComplexity

try:
    import yaml

    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

logger = logging.getLogger(__name__)

# Module-level config cache. ``_load_config`` mutates these via ``global``
# statements, so they must live in the same module as the method.
_config_cache: dict = {}
_config_cache_path: str | None = None


class PromptAssemblerTemplateMixin(PromptAssemblerBase):
    """Provides template variant tables and DevSquad config loading."""

    _TEMPLATE_VARIANTS = {
        TaskComplexity.SIMPLE: {
            "name": "compact",
            "role_truncate": 80,
            "findings_limit": 2,
            "findings_truncate": 60,
            "include_constraints": False,
            "include_anti_patterns": False,
            "instruction_style": "direct",
        },
        TaskComplexity.MEDIUM: {
            "name": "standard",
            "role_truncate": 200,
            "findings_limit": 5,
            "findings_truncate": 150,
            "include_constraints": True,
            "include_anti_patterns": False,
            "instruction_style": "structured",
        },
        TaskComplexity.COMPLEX: {
            "name": "enhanced",
            "role_truncate": 500,
            "findings_limit": 8,
            "findings_truncate": 200,
            "include_constraints": True,
            "include_anti_patterns": True,
            "instruction_style": "comprehensive",
        },
    }

    _COMPRESSION_OVERRIDES = {
        "NONE": {},
        "SNIP": {
            "role_truncate": 120,
            "findings_limit": 3,
            "findings_truncate": 100,
            "include_constraints": False,
            "include_anti_patterns": False,
        },
        "SESSION_MEMORY": {
            "role_truncate": 60,
            "findings_limit": 1,
            "findings_truncate": 50,
            "include_constraints": False,
            "include_anti_patterns": False,
            "instruction_style": "minimal",
        },
        "FULL_COMPACT": {
            "role_truncate": 40,
            "findings_limit": 0,
            "findings_truncate": 0,
            "include_constraints": False,
            "include_anti_patterns": False,
            "instruction_style": "ultra_minimal",
        },
    }

    def _load_config(self, config_path: str | None = None) -> dict:
        """
        Load DevSquad configuration from YAML file.

        Search order:
        1. Explicit config_path parameter
        2. .devsquad.yaml in current directory
        3. .devsquad.yaml in project root (directory with pyproject.toml/.git)
        4. Default empty config (quality control disabled)

        Args:
            config_path: Explicit path to config file

        Returns:
            Dict: Parsed configuration dictionary
        """
        if not _YAML_AVAILABLE:
            return {"quality_control": {"enabled": False}}

        global _config_cache, _config_cache_path

        search_paths = []

        if config_path and os.path.exists(config_path):
            search_paths.append(config_path)
        else:
            current_dir = os.getcwd()
            candidate = os.path.join(current_dir, ".devsquad.yaml")
            if os.path.exists(candidate):
                search_paths.append(candidate)
            else:
                search_dir = current_dir
                for _ in range(5):
                    if os.path.exists(os.path.join(search_dir, "pyproject.toml")) or os.path.exists(
                        os.path.join(search_dir, ".git")
                    ):
                        project_config = os.path.join(search_dir, ".devsquad.yaml")
                        if os.path.exists(project_config):
                            search_paths.append(project_config)
                        break
                    parent = os.path.dirname(search_dir)
                    if parent == search_dir:
                        break
                    search_dir = parent

        if search_paths:
            resolved = os.path.realpath(search_paths[0])
            if _config_cache_path == resolved and _config_cache:
                return _config_cache
            try:
                with open(resolved, encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
                _config_cache = config
                _config_cache_path = resolved
                return config
            except (OSError, PermissionError, ValueError, TypeError) as e:
                logger.warning("Failed to load config from %s: %s", resolved, e)
                return {}
        else:
            return {"quality_control": {"enabled": False}}
