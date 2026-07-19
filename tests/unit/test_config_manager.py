"""Tests for ConfigManager Pydantic strong-typed configuration.

V4.1.2 P1-12 Wave 2: Verifies that ConfigManager:
1. Loads ``.devsquad.yaml`` with full type validation
2. Applies environment variable overrides correctly
3. Falls back to defaults when no file is found
4. Rejects invalid values with clear ValidationError messages
5. Singleton lifecycle (instance reuse, reset, reload)
6. Round-trips with the existing dict-based config reading
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from scripts.collaboration.config_manager import (
    AIQualityControlConfig,
    AISecurityGuardConfig,
    AITeamCollaborationConfig,
    ConfigManager,
    ConsensusConfig,
    DevSquadConfig,
    QualityControlConfig,
)

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def reset_config_singleton():
    """Reset the ConfigManager singleton before and after each test."""
    ConfigManager.reset()
    yield
    ConfigManager.reset()


@pytest.fixture
def sample_yaml_dict() -> dict[str, Any]:
    """A minimal valid YAML config dict for testing."""
    return {
        "quality_control": {
            "enabled": True,
            "strict_mode": False,
            "min_quality_score": 90,
            "ai_quality_control": {
                "enabled": True,
                "hallucination_check": {
                    "enabled": True,
                    "require_traceable_references": False,
                },
            },
            "ai_team_collaboration": {
                "consensus": {
                    "enabled": True,
                    "threshold": 0.8,
                    "weights": {"architect": 2.0, "tester": 1.5},
                },
            },
        },
        "backend": "openai",
        "timeout": 60,
        "max_roles": 5,
        "log_level": "DEBUG",
    }


@pytest.fixture
def sample_yaml_file(tmp_path: Path, sample_yaml_dict: dict[str, Any]) -> Path:
    """Write the sample YAML dict to a temp file and return its path."""
    yaml_path = tmp_path / ".devsquad.yaml"
    with yaml_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(sample_yaml_dict, f)
    return yaml_path


# ---------------------------------------------------------------------------
# DevSquadConfig.from_dict / from_yaml
# ---------------------------------------------------------------------------


class TestDevSquadConfigLoading:
    """Tests for DevSquadConfig.from_dict() and from_yaml()."""

    def test_from_dict_returns_devsquad_config(self, sample_yaml_dict: dict[str, Any]) -> None:
        """from_dict() returns a DevSquadConfig instance."""
        config = DevSquadConfig.from_dict(sample_yaml_dict)
        assert isinstance(config, DevSquadConfig)

    def test_from_dict_preserves_flat_keys(self, sample_yaml_dict: dict[str, Any]) -> None:
        """from_dict() preserves flat key values."""
        config = DevSquadConfig.from_dict(sample_yaml_dict)
        assert config.backend == "openai"
        assert config.timeout == 60
        assert config.max_roles == 5
        assert config.log_level == "DEBUG"

    def test_from_dict_preserves_nested_quality_control(
        self, sample_yaml_dict: dict[str, Any]
    ) -> None:
        """from_dict() preserves nested quality_control structure."""
        config = DevSquadConfig.from_dict(sample_yaml_dict)
        assert config.quality_control.enabled is True
        assert config.quality_control.strict_mode is False
        assert config.quality_control.min_quality_score == 90

    def test_from_dict_preserves_deeply_nested_consensus(
        self, sample_yaml_dict: dict[str, Any]
    ) -> None:
        """from_dict() preserves deeply nested consensus config."""
        config = DevSquadConfig.from_dict(sample_yaml_dict)
        consensus = config.quality_control.ai_team_collaboration.consensus
        assert consensus.enabled is True
        assert consensus.threshold == 0.8
        assert consensus.weights["architect"] == 2.0
        assert consensus.weights["tester"] == 1.5

    def test_from_dict_applies_defaults_for_missing_keys(self) -> None:
        """from_dict() fills in defaults for missing keys."""
        config = DevSquadConfig.from_dict({})
        assert config.backend == "mock"  # default
        assert config.timeout == 120  # default
        assert config.max_roles == 10  # default
        assert config.log_level == "WARNING"  # default
        assert config.quality_control.enabled is True  # default

    def test_from_dict_ignores_unknown_keys(self) -> None:
        """from_dict() silently ignores unknown keys (forward-compat)."""
        config = DevSquadConfig.from_dict({"unknown_key": "value", "backend": "anthropic"})
        assert config.backend == "anthropic"

    def test_from_yaml_loads_file(self, sample_yaml_file: Path) -> None:
        """from_yaml() loads and parses a YAML file."""
        config = DevSquadConfig.from_yaml(sample_yaml_file)
        assert config.backend == "openai"
        assert config.timeout == 60

    def test_from_yaml_raises_on_missing_file(self, tmp_path: Path) -> None:
        """from_yaml() raises FileNotFoundError for missing file."""
        missing = tmp_path / "nonexistent.yaml"
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            DevSquadConfig.from_yaml(missing)

    def test_from_yaml_raises_on_non_mapping_content(self, tmp_path: Path) -> None:
        """from_yaml() raises ValueError if YAML content is not a mapping."""
        bad_path = tmp_path / "bad.yaml"
        bad_path.write_text("- just\n- a\n- list\n", encoding="utf-8")
        with pytest.raises(ValueError, match="must contain a YAML mapping"):
            DevSquadConfig.from_yaml(bad_path)

    def test_from_yaml_handles_empty_file(self, tmp_path: Path) -> None:
        """from_yaml() returns a default config for an empty file."""
        empty_path = tmp_path / "empty.yaml"
        empty_path.write_text("", encoding="utf-8")
        config = DevSquadConfig.from_yaml(empty_path)
        assert config.backend == "mock"  # default
        assert config.timeout == 120  # default


# ---------------------------------------------------------------------------
# Environment variable overrides
# ---------------------------------------------------------------------------


class TestEnvOverrides:
    """Tests for environment variable overrides in from_dict()."""

    def test_env_override_backend(
        self, sample_yaml_dict: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DEVSQUAD_BACKEND overrides the backend flat key."""
        monkeypatch.setenv("DEVSQUAD_BACKEND", "anthropic")
        config = DevSquadConfig.from_dict(sample_yaml_dict)
        assert config.backend == "anthropic"

    def test_env_override_timeout(
        self, sample_yaml_dict: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DEVSQUAD_TIMEOUT overrides the timeout flat key (int conversion)."""
        monkeypatch.setenv("DEVSQUAD_TIMEOUT", "30")
        config = DevSquadConfig.from_dict(sample_yaml_dict)
        assert config.timeout == 30

    def test_env_override_max_roles(
        self, sample_yaml_dict: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DEVSQUAD_MAX_ROLES overrides max_roles (int conversion)."""
        monkeypatch.setenv("DEVSQUAD_MAX_ROLES", "3")
        config = DevSquadConfig.from_dict(sample_yaml_dict)
        assert config.max_roles == 3

    def test_env_override_log_level_normalizes_case(
        self, sample_yaml_dict: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DEVSQUAD_LOG_LEVEL is normalized to upper case."""
        monkeypatch.setenv("DEVSQUAD_LOG_LEVEL", "info")
        config = DevSquadConfig.from_dict(sample_yaml_dict)
        assert config.log_level == "INFO"

    def test_env_override_invalid_int_falls_back_to_yaml(
        self,
        sample_yaml_dict: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Invalid int env var is ignored; YAML value is kept."""
        monkeypatch.setenv("DEVSQUAD_TIMEOUT", "not-an-int")
        with caplog.at_level("WARNING"):
            config = DevSquadConfig.from_dict(sample_yaml_dict)
        # YAML value (60) is kept because env var was invalid
        assert config.timeout == 60

    def test_env_override_does_not_affect_nested_quality_control(
        self,
        sample_yaml_dict: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Env overrides do not affect nested quality_control section."""
        monkeypatch.setenv("DEVSQUAD_BACKEND", "mock")
        config = DevSquadConfig.from_dict(sample_yaml_dict)
        # Flat key overridden
        assert config.backend == "mock"
        # Nested key preserved from YAML
        assert config.quality_control.ai_team_collaboration.consensus.threshold == 0.8


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestConfigValidation:
    """Tests for Pydantic validation constraints."""

    def test_invalid_backend_raises(self) -> None:
        """Invalid backend value raises ValidationError."""
        with pytest.raises(ValidationError, match="backend must be one of"):
            DevSquadConfig.from_dict({"backend": "invalid_backend"})

    def test_invalid_output_format_raises(self) -> None:
        """Invalid output_format raises ValidationError."""
        with pytest.raises(ValidationError, match="output_format must be one of"):
            DevSquadConfig.from_dict({"output_format": "xml"})

    def test_invalid_log_level_raises(self) -> None:
        """Invalid log_level raises ValidationError."""
        with pytest.raises(ValidationError, match="log_level must be one of"):
            DevSquadConfig.from_dict({"log_level": "VERBOSE"})

    def test_invalid_permission_level_raises(self) -> None:
        """Invalid permission_level in ai_security_guard raises ValidationError."""
        with pytest.raises(ValidationError, match="permission_level must be one of"):
            DevSquadConfig.from_dict(
                {
                    "quality_control": {
                        "ai_security_guard": {"permission_level": "SUPERUSER"},
                    }
                }
            )

    def test_negative_timeout_raises(self) -> None:
        """Negative timeout raises ValidationError."""
        with pytest.raises(ValidationError):
            DevSquadConfig.from_dict({"timeout": -1})

    def test_zero_max_roles_raises(self) -> None:
        """max_roles=0 raises ValidationError (must be >= 1)."""
        with pytest.raises(ValidationError):
            DevSquadConfig.from_dict({"max_roles": 0})

    def test_consensus_threshold_out_of_range_raises(self) -> None:
        """consensus threshold > 1.0 raises ValidationError."""
        with pytest.raises(ValidationError):
            DevSquadConfig.from_dict(
                {
                    "quality_control": {
                        "ai_team_collaboration": {
                            "consensus": {"threshold": 1.5},
                        }
                    }
                }
            )

    def test_min_quality_score_out_of_range_raises(self) -> None:
        """min_quality_score > 100 raises ValidationError."""
        with pytest.raises(ValidationError):
            DevSquadConfig.from_dict(
                {"quality_control": {"min_quality_score": 150}}
            )


# ---------------------------------------------------------------------------
# Defaults and types
# ---------------------------------------------------------------------------


class TestConfigDefaults:
    """Tests for default values and types."""

    def test_defaults_match_yaml_defaults(self) -> None:
        """Defaults match the values documented in .devsquad.yaml comments."""
        config = DevSquadConfig()
        assert config.backend == "mock"
        assert config.base_url == ""
        assert config.model == ""
        assert config.timeout == 120
        assert config.max_roles == 10
        assert config.max_task_length == 10000
        assert config.min_task_length == 5
        assert config.strict_validation is False
        assert config.output_format == "structured"
        assert config.checkpoint_enabled is True
        assert config.checkpoint_dir == "./checkpoints"
        assert config.workflow_enabled is False
        assert config.cache_enabled is True
        assert config.log_level == "WARNING"
        assert config.smart_compression is False
        assert config.ccr_store_path is None
        assert config.token_budget_total is None

    def test_default_consensus_weights_align_with_role_weights(self) -> None:
        """Default consensus weights align with ROLE_WEIGHTS in models_dispatch.

        This is a critical alignment check — the YAML mirror must match the
        code-side canonical source.
        """
        from scripts.collaboration.models_dispatch import ROLE_WEIGHTS

        config = DevSquadConfig()
        assert config.quality_control.ai_team_collaboration.consensus.weights == ROLE_WEIGHTS

    def test_default_quality_control_subconfigs_are_enabled(self) -> None:
        """Default quality control sub-systems are all enabled."""
        config = DevSquadConfig()
        qc = config.quality_control
        assert qc.enabled is True
        assert qc.ai_quality_control.enabled is True
        assert qc.ai_security_guard.enabled is True
        assert qc.ai_team_collaboration.enabled is True

    def test_types_are_correct(self) -> None:
        """All fields have the correct Python types."""
        config = DevSquadConfig()
        assert isinstance(config.quality_control, QualityControlConfig)
        assert isinstance(config.quality_control.ai_quality_control, AIQualityControlConfig)
        assert isinstance(config.quality_control.ai_security_guard, AISecurityGuardConfig)
        assert isinstance(
            config.quality_control.ai_team_collaboration, AITeamCollaborationConfig
        )
        assert isinstance(
            config.quality_control.ai_team_collaboration.consensus, ConsensusConfig
        )
        assert isinstance(config.timeout, int)
        assert isinstance(config.max_roles, int)
        assert isinstance(config.backend, str)


# ---------------------------------------------------------------------------
# ConfigManager singleton
# ---------------------------------------------------------------------------


class TestConfigManagerSingleton:
    """Tests for ConfigManager singleton behavior."""

    def test_singleton_returns_same_instance(
        self, reset_config_singleton: None, tmp_path: Path, sample_yaml_dict: dict[str, Any]
    ) -> None:
        """ConfigManager() returns the same instance on repeated calls."""
        yaml_path = tmp_path / ".devsquad.yaml"
        with yaml_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(sample_yaml_dict, f)

        mgr1 = ConfigManager(yaml_path)
        mgr2 = ConfigManager()  # No path — should return existing instance
        assert mgr1 is mgr2

    def test_reset_clears_singleton(
        self, reset_config_singleton: None, tmp_path: Path, sample_yaml_dict: dict[str, Any]
    ) -> None:
        """ConfigManager.reset() clears the singleton."""
        yaml_path = tmp_path / ".devsquad.yaml"
        with yaml_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(sample_yaml_dict, f)

        mgr1 = ConfigManager(yaml_path)
        ConfigManager.reset()
        mgr2 = ConfigManager()
        assert mgr1 is not mgr2

    def test_reload_picks_up_changes(
        self,
        reset_config_singleton: None,
        tmp_path: Path,
        sample_yaml_dict: dict[str, Any],
    ) -> None:
        """reload() picks up changes to the YAML file."""
        yaml_path = tmp_path / ".devsquad.yaml"
        with yaml_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(sample_yaml_dict, f)

        mgr = ConfigManager(yaml_path)
        assert mgr.config.timeout == 60

        # Modify the file
        sample_yaml_dict["timeout"] = 99
        with yaml_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(sample_yaml_dict, f)

        mgr.reload()
        assert mgr.config.timeout == 99

    def test_config_path_property(
        self,
        reset_config_singleton: None,
        tmp_path: Path,
        sample_yaml_dict: dict[str, Any],
    ) -> None:
        """config_path property returns the loaded file path."""
        yaml_path = tmp_path / ".devsquad.yaml"
        with yaml_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(sample_yaml_dict, f)

        mgr = ConfigManager(yaml_path)
        assert mgr.config_path == yaml_path

    def test_default_config_when_no_file_found(
        self,
        reset_config_singleton: None,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ConfigManager uses defaults when no .devsquad.yaml is found."""
        # Change to an empty directory and clear env vars
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DEVSQUAD_CONFIG_PATH", raising=False)
        # Make sure no .devsquad.yaml exists in tmp_path
        assert not (tmp_path / ".devsquad.yaml").exists()

        mgr = ConfigManager()
        assert mgr.config_path is None
        assert mgr.config.backend == "mock"  # default


# ---------------------------------------------------------------------------
# Real .devsquad.yaml integration
# ---------------------------------------------------------------------------


class TestRealDevsquadYaml:
    """Integration test: load the actual project .devsquad.yaml file.

    This verifies that the Pydantic schema matches the real config file
    used by the project.
    """

    def test_load_real_devsquad_yaml(self) -> None:
        """The real .devsquad.yaml loads without errors."""
        project_root = Path(__file__).parent.parent.parent
        yaml_path = project_root / ".devsquad.yaml"
        if not yaml_path.exists():
            pytest.skip(".devsquad.yaml not found at project root")

        config = DevSquadConfig.from_yaml(yaml_path)
        # Spot-check a few values from the real file
        assert config.backend in {"mock", "openai", "anthropic", "moka", "trae", "fallback", "auto"}
        assert config.timeout >= 1
        assert config.max_roles >= 1
        assert config.quality_control.enabled is True
        assert config.quality_control.ai_quality_control.enabled is True
        assert config.quality_control.ai_security_guard.enabled is True
        assert config.quality_control.ai_team_collaboration.enabled is True

    def test_real_yaml_consensus_weights_align_with_role_weights(self) -> None:
        """The real .devsquad.yaml consensus weights match ROLE_WEIGHTS."""
        project_root = Path(__file__).parent.parent.parent
        yaml_path = project_root / ".devsquad.yaml"
        if not yaml_path.exists():
            pytest.skip(".devsquad.yaml not found at project root")

        from scripts.collaboration.models_dispatch import ROLE_WEIGHTS

        config = DevSquadConfig.from_yaml(yaml_path)
        assert config.quality_control.ai_team_collaboration.consensus.weights == ROLE_WEIGHTS
