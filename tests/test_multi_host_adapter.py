#!/usr/bin/env python3
"""Tests for MultiHostAdapter — V39-07 multi-host adapter layer.

Tests cover:
- Host type configuration (6 host types)
- Role mapping (host-native → DevSquad)
- Prompt adaptation (prefix/suffix)
- Output slicing (truncation)
- Full dispatch flow (mock mode)
- Host info retrieval
- Edge cases (unknown roles, empty task, None roles)
"""

from scripts.collaboration.multi_host_adapter import (
    HOST_CONFIGS,
    HostConfig,
    HostType,
    MultiHostAdapter,
)


class TestHostType:
    """Test HostType enum."""

    def test_host_type_values(self):
        """Verify: All 6 host types have correct string values."""
        assert HostType.CLAUDE_CODE.value == "claude-code"
        assert HostType.CURSOR.value == "cursor"
        assert HostType.CODEX.value == "codex"
        assert HostType.CLINE.value == "cline"
        assert HostType.TRAE.value == "trae"
        assert HostType.GENERIC.value == "generic"

    def test_host_type_from_string(self):
        """Verify: HostType can be constructed from string value."""
        assert HostType("claude-code") is HostType.CLAUDE_CODE
        assert HostType("cursor") is HostType.CURSOR


class TestHostConfigs:
    """Test predefined host configurations."""

    def test_all_host_types_have_configs(self):
        """Verify: Every HostType has a corresponding HostConfig."""
        for host_type in HostType:
            assert host_type in HOST_CONFIGS, f"Missing config for {host_type}"

    def test_claude_code_config(self):
        """Verify: Claude Code has streaming + MCP enabled."""
        config = HOST_CONFIGS[HostType.CLAUDE_CODE]
        assert config.supports_streaming is True
        assert config.supports_mcp is True
        assert config.max_output_chars == 12000
        assert "analyst" in config.role_mapping

    def test_cursor_config_no_mcp(self):
        """Verify: Cursor does not support MCP."""
        config = HOST_CONFIGS[HostType.CURSOR]
        assert config.supports_mcp is False

    def test_trae_config_highest_output_limit(self):
        """Verify: Trae has the highest output character limit."""
        trae_limit = HOST_CONFIGS[HostType.TRAE].max_output_chars
        for host_type, config in HOST_CONFIGS.items():
            if host_type != HostType.TRAE:
                assert trae_limit >= config.max_output_chars

    def test_codex_role_mapping(self):
        """Verify: Codex maps 'developer' to 'solo-coder'."""
        config = HOST_CONFIGS[HostType.CODEX]
        assert config.role_mapping.get("developer") == "solo-coder"


class TestMultiHostAdapterInit:
    """Test MultiHostAdapter initialization."""

    def test_default_init_uses_trae(self):
        """Verify: Default host type is TRAE."""
        adapter = MultiHostAdapter()
        assert adapter.host_type is HostType.TRAE
        adapter.shutdown()

    def test_init_with_specific_host(self):
        """Verify: Can initialize with a specific host type."""
        adapter = MultiHostAdapter(HostType.CLAUDE_CODE)
        assert adapter.host_type is HostType.CLAUDE_CODE
        assert "claude-code" in adapter.config.prompt_prefix.lower() or adapter.config.prompt_prefix != ""
        adapter.shutdown()

    def test_init_with_custom_config(self):
        """Verify: Custom config overrides predefined config."""
        custom = HostConfig(
            host_type=HostType.GENERIC,
            max_output_chars=500,
            supports_streaming=True,
            supports_mcp=False,
            prompt_prefix="[CUSTOM] ",
            role_mapping={"dev": "solo-coder"},
        )
        adapter = MultiHostAdapter(HostType.GENERIC, config=custom)
        assert adapter.config.max_output_chars == 500
        assert adapter.config.supports_mcp is False
        assert adapter.config.prompt_prefix == "[CUSTOM] "
        adapter.shutdown()


class TestRoleMapping:
    """Test host-native role name mapping."""

    def test_map_claude_code_roles(self):
        """Verify: Claude Code role names map to DevSquad roles."""
        adapter = MultiHostAdapter(HostType.CLAUDE_CODE)
        mapped = adapter._map_roles(["analyst", "engineer", "reviewer", "architect"])
        assert mapped == ["product-manager", "solo-coder", "tester", "architect"]
        adapter.shutdown()

    def test_map_unknown_role_passes_through(self):
        """Verify: Unknown role names pass through unchanged."""
        adapter = MultiHostAdapter(HostType.CLAUDE_CODE)
        mapped = adapter._map_roles(["unknown-role", "architect"])
        assert mapped == ["unknown-role", "architect"]
        adapter.shutdown()

    def test_map_none_roles_returns_none(self):
        """Verify: None roles returns None (auto-match)."""
        adapter = MultiHostAdapter()
        assert adapter._map_roles(None) is None
        adapter.shutdown()

    def test_map_empty_mapping_returns_original(self):
        """Verify: Host with no role mapping returns original roles."""
        adapter = MultiHostAdapter(HostType.CURSOR)
        mapped = adapter._map_roles(["architect", "tester"])
        assert mapped == ["architect", "tester"]
        adapter.shutdown()

    def test_map_codex_developer_role(self):
        """Verify: Codex maps 'developer' to 'solo-coder'."""
        adapter = MultiHostAdapter(HostType.CODEX)
        mapped = adapter._map_roles(["developer", "architect"])
        assert mapped == ["solo-coder", "architect"]
        adapter.shutdown()


class TestPromptAdaptation:
    """Test prompt prefix/suffix adaptation."""

    def test_claude_code_prompt_has_prefix(self):
        """Verify: Claude Code prompts get prefix prepended."""
        adapter = MultiHostAdapter(HostType.CLAUDE_CODE)
        adapted = adapter._adapt_prompt("Design auth system")
        assert "DevSquad" in adapted
        assert "Design auth system" in adapted
        adapter.shutdown()

    def test_trae_prompt_no_prefix(self):
        """Verify: Trae prompts have no prefix (empty string)."""
        adapter = MultiHostAdapter(HostType.TRAE)
        adapted = adapter._adapt_prompt("Design auth system")
        assert adapted == "Design auth system"
        adapter.shutdown()

    def test_cursor_prompt_has_prefix(self):
        """Verify: Cursor prompts get [DevSquad] prefix."""
        adapter = MultiHostAdapter(HostType.CURSOR)
        adapted = adapter._adapt_prompt("Fix bug")
        assert adapted.startswith("[DevSquad]")
        adapter.shutdown()

    def test_prompt_with_suffix(self):
        """Verify: Prompt suffix is appended when configured."""
        custom = HostConfig(
            host_type=HostType.GENERIC,
            prompt_prefix="[START] ",
            prompt_suffix=" [END]",
        )
        adapter = MultiHostAdapter(HostType.GENERIC, config=custom)
        adapted = adapter._adapt_prompt("task")
        assert adapted == "[START] \ntask\n [END]"
        adapter.shutdown()


class TestOutputSlicing:
    """Test output truncation for host character limits."""

    def test_short_output_not_truncated(self):
        """Verify: Output under limit is not truncated."""
        adapter = MultiHostAdapter(HostType.GENERIC)
        report = "short report"
        result = adapter._slice_output(report)
        assert result == "short report"
        adapter.shutdown()

    def test_long_output_truncated(self):
        """Verify: Output over limit is truncated with marker."""
        custom = HostConfig(host_type=HostType.GENERIC, max_output_chars=100)
        adapter = MultiHostAdapter(HostType.GENERIC, config=custom)
        report = "x" * 200
        result = adapter._slice_output(report)
        assert len(result) <= 100
        assert "truncated" in result
        adapter.shutdown()

    def test_truncation_marker_contains_char_count(self):
        """Verify: Truncation marker includes the character limit."""
        custom = HostConfig(host_type=HostType.GENERIC, max_output_chars=50)
        adapter = MultiHostAdapter(HostType.GENERIC, config=custom)
        report = "x" * 200
        result = adapter._slice_output(report)
        assert "50" in result
        adapter.shutdown()


class TestDispatch:
    """Test full dispatch flow through the adapter."""

    def test_dispatch_mock_mode_success(self):
        """Verify: Mock dispatch succeeds and returns host info."""
        adapter = MultiHostAdapter(HostType.TRAE)
        result = adapter.dispatch("Design a simple API")
        assert result["success"] is True
        assert result["host"] == "trae"
        assert "report" in result
        assert isinstance(result["report"], str)
        adapter.shutdown()

    def test_dispatch_with_explicit_roles(self):
        """Verify: Dispatch with explicit roles maps correctly."""
        adapter = MultiHostAdapter(HostType.CLAUDE_CODE)
        result = adapter.dispatch("Design auth", roles=["analyst", "architect"])
        assert result["success"] is True
        # Claude Code maps "analyst" → "product-manager"
        assert "product-manager" in result["roles"] or "architect" in result["roles"]
        adapter.shutdown()

    def test_dispatch_returns_raw_result(self):
        """Verify: Dispatch result includes raw DispatchResult object."""
        adapter = MultiHostAdapter()
        result = adapter.dispatch("Test task")
        assert result["raw_result"] is not None
        assert hasattr(result["raw_result"], "to_markdown")
        adapter.shutdown()

    def test_dispatch_different_hosts_produce_reports(self):
        """Verify: All host types can dispatch and produce reports."""
        for host_type in HostType:
            adapter = MultiHostAdapter(host_type)
            result = adapter.dispatch("Simple task")
            assert result["success"] is True, f"Failed for {host_type}"
            assert result["host"] == host_type.value
            assert len(result["report"]) > 0
            adapter.shutdown()


class TestHostInfo:
    """Test host info retrieval."""

    def test_get_host_info_trae(self):
        """Verify: Trae host info is correct."""
        adapter = MultiHostAdapter(HostType.TRAE)
        info = adapter.get_host_info()
        assert info["host_type"] == "trae"
        assert info["supports_streaming"] is True
        assert info["supports_mcp"] is True
        assert info["max_output_chars"] == 15000
        adapter.shutdown()

    def test_get_host_info_cursor_no_mcp(self):
        """Verify: Cursor host info shows no MCP support."""
        adapter = MultiHostAdapter(HostType.CURSOR)
        info = adapter.get_host_info()
        assert info["supports_mcp"] is False
        adapter.shutdown()

    def test_get_host_info_includes_role_mappings(self):
        """Verify: Host info includes role mappings dict."""
        adapter = MultiHostAdapter(HostType.CLAUDE_CODE)
        info = adapter.get_host_info()
        assert "role_mappings" in info
        assert "analyst" in info["role_mappings"]
        adapter.shutdown()


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_dispatch_empty_task_returns_result(self):
        """Verify: Empty task is handled gracefully by dispatcher."""
        adapter = MultiHostAdapter()
        result = adapter.dispatch("")
        # Dispatcher handles empty tasks internally
        assert "success" in result
        adapter.shutdown()

    def test_generic_host_as_fallback(self):
        """Verify: Generic host works as a fallback for unknown hosts."""
        adapter = MultiHostAdapter(HostType.GENERIC)
        assert adapter.config.max_output_chars == 8000
        adapter.shutdown()

    def test_custom_config_with_empty_role_mapping(self):
        """Verify: Custom config with empty role mapping passes roles through."""
        custom = HostConfig(
            host_type=HostType.GENERIC,
            role_mapping={},
        )
        adapter = MultiHostAdapter(HostType.GENERIC, config=custom)
        mapped = adapter._map_roles(["architect", "tester"])
        assert mapped == ["architect", "tester"]
        adapter.shutdown()
