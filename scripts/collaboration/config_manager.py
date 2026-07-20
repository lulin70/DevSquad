"""ConfigManager — Pydantic-based typed configuration for DevSquad.

V4.1.2 P1-12: Replaces ad-hoc dict-based config reading with strong types.

This module is introduced in **Wave 2 Phase 3** as a parallel-to-existing
configuration layer. Existing modules continue to read ``.devsquad.yaml``
via ``dict.get()`` patterns; ``ConfigManager`` provides a typed alternative
that new code can opt into. Full migration of existing modules is deferred
to V4.2.0 (see ``docs/audits/V4.1.2_Phase3_Plan.md`` §2.2).

Usage:
    from scripts.collaboration.config_manager import ConfigManager

    mgr = ConfigManager()                       # auto-discovers .devsquad.yaml
    config = mgr.config                         # DevSquadConfig instance
    threshold = config.quality_control.ai_team_collaboration.consensus.threshold
    weights = config.quality_control.ai_team_collaboration.consensus.weights

YAML file format (see ``.devsquad.yaml`` for canonical reference):
    quality_control:
      enabled: true
      ai_quality_control:
        hallucination_check: { enabled: true, ... }
      ai_team_collaboration:
        consensus:
          threshold: 0.7
          weights: { architect: 1.5, ... }
    backend: "mock"
    timeout: 120
    # ... (all flat keys)

Environment variable overrides:
    DEVSQUAD_BACKEND, DEVSQUAD_BASE_URL, DEVSQUAD_MODEL, DEVSQUAD_TIMEOUT,
    DEVSQUAD_MAX_ROLES, DEVSQUAD_LOG_LEVEL — each overrides the
    corresponding flat key when set. Nested ``quality_control.*`` keys
    are not env-overridable (use the YAML file).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AI Quality Control sub-configs
# ---------------------------------------------------------------------------


class HallucinationCheckConfig(BaseModel):
    """Hallucination detection settings."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    require_traceable_references: bool = True
    require_signature_verification: bool = True
    forbid_absolute_certainty: bool = True


class OverconfidenceCheckConfig(BaseModel):
    """Overconfidence detection settings."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    require_alternatives_min: int = Field(default=2, ge=0)
    require_failure_scenarios_min: int = Field(default=3, ge=0)
    acknowledge_tradeoffs: bool = True


class PatternDiversityConfig(BaseModel):
    """Pattern diversity settings (anti-rigidity)."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    check_frequency_every_n_dispatches: int = Field(default=10, ge=1)
    warn_on_overused_patterns: bool = True


class SelfVerificationPreventionConfig(BaseModel):
    """Self-verification trap prevention (creator/tester separation)."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    enforce_creator_tester_separation: bool = True
    require_spec_based_testing: bool = True
    min_error_coverage_percent: int = Field(default=15, ge=0, le=100)


class AIQualityControlConfig(BaseModel):
    """AI-specific quality control sub-system."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    hallucination_check: HallucinationCheckConfig = Field(default_factory=HallucinationCheckConfig)
    overconfidence_check: OverconfidenceCheckConfig = Field(default_factory=OverconfidenceCheckConfig)
    pattern_diversity: PatternDiversityConfig = Field(default_factory=PatternDiversityConfig)
    self_verification_prevention: SelfVerificationPreventionConfig = Field(
        default_factory=SelfVerificationPreventionConfig
    )


# ---------------------------------------------------------------------------
# AI Security Guard sub-configs
# ---------------------------------------------------------------------------


class InputValidationConfig(BaseModel):
    """Input validation settings (prompt-injection / OWASP)."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    block_high_severity: bool = True
    warn_and_sanitize_medium: bool = True
    flag_low_severity: bool = True


class SecurityReviewConfig(BaseModel):
    """Security review settings (auto-trigger / veto)."""

    model_config = ConfigDict(extra="ignore")

    auto_trigger_when_security_role: bool = True
    veto_enabled: bool = True
    block_on_critical_finding: bool = True


class AuditLoggingConfig(BaseModel):
    """Audit logging settings."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    log_operations: bool = True
    log_filesystem_access: bool = True
    log_network_requests: bool = True
    retention_days: int = Field(default=90, ge=1)


class AISecurityGuardConfig(BaseModel):
    """AI security guard sub-system."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    permission_level: str = "DEFAULT"
    input_validation: InputValidationConfig = Field(default_factory=InputValidationConfig)
    security_review: SecurityReviewConfig = Field(default_factory=SecurityReviewConfig)
    audit_logging: AuditLoggingConfig = Field(default_factory=AuditLoggingConfig)

    @field_validator("permission_level")
    @classmethod
    def _validate_permission_level(cls, v: str) -> str:
        allowed = {"PLAN", "DEFAULT", "AUTO", "BYPASS"}
        if v not in allowed:
            raise ValueError(
                f"permission_level must be one of {allowed!r}, got {v!r}"
            )
        return v


# ---------------------------------------------------------------------------
# AI Team Collaboration sub-configs
# ---------------------------------------------------------------------------


class RaciConfig(BaseModel):
    """RACI matrix settings (PLANNED — not yet enforced in code).

    Kept for forward-compat; code currently ignores these keys.
    """

    model_config = ConfigDict(extra="ignore")

    mode: str = "strict"
    enforce_one_responsible: bool = True
    enforce_one_accountable: bool = True
    allow_a_override_r: bool = True


class ScratchpadConfig(BaseModel):
    """Scratchpad zoned-protocol settings (PLANNED — not yet enforced)."""

    model_config = ConfigDict(extra="ignore")

    protocol: str = "zoned"
    forbid_cross_zone_writes: bool = True
    forbid_sensitive_in_shared: bool = True


class ConsensusConfig(BaseModel):
    """Consensus engine settings.

    ``weights`` MUST align with ``scripts/collaboration/models_dispatch.py:ROLE_WEIGHTS``.
    Canonical source = ``ROLE_WEIGHTS`` (code-side); this YAML mirror is for
    visibility only.
    """

    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    weights: dict[str, float] = Field(
        default_factory=lambda: {
            "architect": 1.5,
            "security": 1.1,
            "product-manager": 1.2,
            "tester": 1.0,
            "solo-coder": 1.0,
            "devops": 1.0,
            "ui-designer": 0.9,
        }
    )
    veto_enabled: bool = True
    veto_allowed_roles: list[str] = Field(default_factory=lambda: ["security", "architect"])
    escalation_policy: str = "auto"
    escalation_timeout_seconds: int = Field(default=300, ge=1)


class ParallelExecutionConfig(BaseModel):
    """Parallel execution safety settings."""

    model_config = ConfigDict(extra="ignore")

    require_file_ownership_declaration: bool = True
    forbid_same_file_writes: bool = True


class AITeamCollaborationConfig(BaseModel):
    """AI team collaboration sub-system."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    raci: RaciConfig = Field(default_factory=RaciConfig)
    scratchpad: ScratchpadConfig = Field(default_factory=ScratchpadConfig)
    consensus: ConsensusConfig = Field(default_factory=ConsensusConfig)
    parallel_execution: ParallelExecutionConfig = Field(default_factory=ParallelExecutionConfig)


# ---------------------------------------------------------------------------
# Top-level Quality Control config
# ---------------------------------------------------------------------------


class QualityControlConfig(BaseModel):
    """Top-level quality control configuration.

    Read by ``PromptAssembler`` for QC rule injection into worker prompts.
    """

    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    strict_mode: bool = True
    min_quality_score: int = Field(default=85, ge=0, le=100)
    minimal_implementation: bool = True
    ponytail_markers: bool = True
    ai_quality_control: AIQualityControlConfig = Field(default_factory=AIQualityControlConfig)
    ai_security_guard: AISecurityGuardConfig = Field(default_factory=AISecurityGuardConfig)
    ai_team_collaboration: AITeamCollaborationConfig = Field(
        default_factory=AITeamCollaborationConfig
    )


# ---------------------------------------------------------------------------
# Top-level DevSquad config
# ---------------------------------------------------------------------------


class DevSquadConfig(BaseModel):
    """Top-level DevSquad configuration (mirrors ``.devsquad.yaml``).

    All flat keys (backend, timeout, etc.) are exposed as top-level fields.
    The nested ``quality_control`` section is exposed as a typed sub-model.

    Environment variable overrides (applied after YAML load):
        DEVSQUAD_BACKEND, DEVSQUAD_BASE_URL, DEVSQUAD_MODEL, DEVSQUAD_TIMEOUT,
        DEVSQUAD_MAX_ROLES, DEVSQUAD_LOG_LEVEL
    """

    model_config = ConfigDict(extra="ignore")

    # Nested quality control section
    quality_control: QualityControlConfig = Field(default_factory=QualityControlConfig)

    # LLM Backend (flat keys)
    backend: str = "mock"
    base_url: str = ""
    model: str = ""
    timeout: int = Field(default=120, ge=1)

    # Task Limits
    max_roles: int = Field(default=10, ge=1)
    max_task_length: int = Field(default=10000, ge=1)
    min_task_length: int = Field(default=5, ge=1)

    # Validation
    strict_validation: bool = False
    output_format: str = "structured"

    # Checkpoint
    checkpoint_enabled: bool = True
    checkpoint_dir: str = "./checkpoints"

    # Workflow
    workflow_enabled: bool = False
    workflow_dir: str = "./workflows"

    # Cache
    cache_enabled: bool = True
    cache_dir: str = "./data/llm_cache"

    # Logging
    log_level: str = "WARNING"

    # V3.10.0 Compression Enhancements
    smart_compression: bool = False
    ccr_store_path: str | None = None
    token_budget_total: int | None = Field(default=None, ge=1)

    @field_validator("backend")
    @classmethod
    def _validate_backend(cls, v: str) -> str:
        allowed = {"mock", "openai", "anthropic", "moka", "trae", "fallback", "auto"}
        if v not in allowed:
            raise ValueError(
                f"backend must be one of {allowed!r}, got {v!r}"
            )
        return v

    @field_validator("output_format")
    @classmethod
    def _validate_output_format(cls, v: str) -> str:
        allowed = {"structured", "compact", "detailed", "json"}
        if v not in allowed:
            raise ValueError(
                f"output_format must be one of {allowed!r}, got {v!r}"
            )
        return v

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(
                f"log_level must be one of {allowed!r}, got {v!r}"
            )
        return v_upper

    # ------------------------------------------------------------------
    # Loaders
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DevSquadConfig:
        """Build a ``DevSquadConfig`` from a parsed dict (e.g. from YAML).

        Applies environment-variable overrides for supported flat keys.
        Unknown keys are silently ignored (forward-compat for future YAML
        additions).
        """
        # Defensive copy so we don't mutate caller's dict
        merged = dict(data)
        cls._apply_env_overrides(merged)
        return cls.model_validate(merged)

    @classmethod
    def from_yaml(cls, path: str | Path) -> DevSquadConfig:
        """Load and validate a YAML config file.

        Args:
            path: Path to the YAML config file.

        Raises:
            FileNotFoundError: If the file does not exist.
            yaml.YAMLError: If the file is not valid YAML.
            pydantic.ValidationError: If the content fails schema validation.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError(
                f"Config file {path} must contain a YAML mapping at the top level, "
                f"got {type(data).__name__}"
            )
        return cls.from_dict(data)

    @staticmethod
    def _apply_env_overrides(merged: dict[str, Any]) -> None:
        """Apply environment variable overrides in-place on ``merged``.

        Only flat keys are env-overridable. Nested ``quality_control.*`` keys
        are not (use the YAML file).

        Supported env vars:
            DEVSQUAD_BACKEND, DEVSQUAD_BASE_URL, DEVSQUAD_MODEL,
            DEVSQUAD_TIMEOUT, DEVSQUAD_MAX_ROLES, DEVSQUAD_LOG_LEVEL
        """
        env_map: dict[str, tuple[str, type]] = {
            "DEVSQUAD_BACKEND": ("backend", str),
            "DEVSQUAD_BASE_URL": ("base_url", str),
            "DEVSQUAD_MODEL": ("model", str),
            "DEVSQUAD_TIMEOUT": ("timeout", int),
            "DEVSQUAD_MAX_ROLES": ("max_roles", int),
            "DEVSQUAD_LOG_LEVEL": ("log_level", str),
        }
        for env_key, (yaml_key, target_type) in env_map.items():
            env_val = os.environ.get(env_key)
            if env_val is None:
                continue
            try:
                if target_type is int:
                    merged[yaml_key] = int(env_val)
                else:
                    merged[yaml_key] = env_val
            except ValueError:
                logger.warning(
                    "Ignoring invalid env var %s=%r (expected %s)",
                    env_key,
                    env_val,
                    target_type.__name__,
                )


# ---------------------------------------------------------------------------
# ConfigManager singleton
# ---------------------------------------------------------------------------


def _default_config_search_paths() -> list[Path]:
    """Return the default search paths for ``.devsquad.yaml``.

    Order:
        1. ``$DEVSQUAD_CONFIG_PATH`` (if set)
        2. ``./.devsquad.yaml`` (current working directory)
        3. Project root: walk up from CWD looking for ``pyproject.toml`` or
           ``.git`` and use that directory's ``.devsquad.yaml``
    """
    paths: list[Path] = []
    env_path = os.environ.get("DEVSQUAD_CONFIG_PATH")
    if env_path:
        paths.append(Path(env_path))
    paths.append(Path.cwd() / ".devsquad.yaml")
    # Walk up to find project root
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
            paths.append(parent / ".devsquad.yaml")
            break
    return paths


class ConfigManager:
    """Singleton config manager.

    Auto-discovers ``.devsquad.yaml`` using ``_default_config_search_paths()``.
    Falls back to a default ``DevSquadConfig()`` if no file is found.

    Thread-safe: the singleton instance is protected by a lock. The
    underlying ``DevSquadConfig`` is immutable (Pydantic v2 BaseModel), so
    concurrent reads are safe without additional locking.
    """

    _instance: ConfigManager | None = None
    _instance_lock = __import__("threading").Lock()

    def __new__(cls, config_path: str | Path | None = None) -> ConfigManager:
        """Return the singleton instance.

        Note: ``config_path`` is only honored on first construction. Subsequent
        calls return the existing instance regardless of ``config_path``. To
        force a reload with a different path, call ``ConfigManager.reset()``
        first.
        """
        with cls._instance_lock:
            if cls._instance is None:
                inst = super().__new__(cls)
                inst._init(config_path)
                cls._instance = inst
            return cls._instance

    def _init(self, config_path: str | Path | None) -> None:
        """Initialize the manager (called once via __new__)."""
        self._config_path: Path | None = None
        self._config: DevSquadConfig
        if config_path is not None:
            self._config_path = Path(config_path)
            self._config = DevSquadConfig.from_yaml(self._config_path)
        else:
            # Auto-discover
            for candidate in _default_config_search_paths():
                if candidate.exists():
                    self._config_path = candidate
                    self._config = DevSquadConfig.from_yaml(candidate)
                    break
            else:
                # No config file found — use defaults
                self._config_path = None
                self._config = DevSquadConfig()
                logger.debug(
                    "No .devsquad.yaml found in search paths; using default config"
                )

    @property
    def config(self) -> DevSquadConfig:
        """The loaded ``DevSquadConfig`` instance."""
        return self._config

    @property
    def config_path(self) -> Path | None:
        """Path to the loaded config file, or ``None`` if using defaults."""
        return self._config_path

    def reload(self, config_path: str | Path | None = None) -> None:
        """Reload config from disk.

        Args:
            config_path: If provided, load from this path. If ``None``,
                reuses the previously-loaded path (if any); otherwise
                re-runs auto-discovery.
        """
        with self._instance_lock:
            if config_path is not None:
                self._config_path = Path(config_path)
                self._config = DevSquadConfig.from_yaml(self._config_path)
            elif self._config_path is not None:
                # Re-load from the previously-loaded path
                self._config = DevSquadConfig.from_yaml(self._config_path)
            else:
                # No previous path — re-run auto-discovery
                self._init(None)

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (primarily for testing)."""
        with cls._instance_lock:
            cls._instance = None
