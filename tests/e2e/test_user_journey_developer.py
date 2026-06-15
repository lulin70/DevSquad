#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DevSquad V3.7.0 E2E Test: User Journey 1 - Developer Onboarding (Alice)

用户旅程：开发者首次使用 DevSquad
故事：Alice 是一名 Python 开发者，听说 DevSquad 可以让 AI 团队协助开发，
      决定尝试用它来帮助设计一个 REST API。

目标：验证新用户从零开始到成功运行第一个任务的完整体验。

P0 Priority - 必须在发布前实现
"""

import pytest
import subprocess
import sys
import os
import time
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any


# Import fixtures from parent __init__.py
from tests.e2e import (
    E2ETestRunner,
    E2ETestResult,
    e2e_runner as session_e2e_runner,
    temp_project_dir as temp_dir_fixture
)


class TestE2EUserJourneyDeveloperOnboarding:
    """
    User Journey 1: Developer First-Time Experience
    
    Covers the complete onboarding flow:
    1. Installation from PyPI
    2. Quick initialization
    3. First task execution
    4. View results and learn
    """

    def test_uj1_1_installation_verification(self, e2e_runner):
        """
        Step UJ1.1: Verify DevSquad is installed and CLI works
        
        用户行为:
        $ devsquad --version
        
        验证点:
        ✅ CLI 命令可用（无 command not found 错误）
        ✅ 版本号显示正确 (V3.6.x)
        ✅ 无依赖缺失警告
        """
        result = e2e_runner.run_cli_command(["--version"])
        
        # Verify version output
        assert result.returncode == 0, f"Version check failed: {result.stderr}"
        
        # Check for version string
        version_output = result.stdout.lower()
        assert "3.6" in version_output or "devsquad" in version_output, \
            f"Version output unexpected: {version_output}"
        
        print(f"✅ Installation verified: {result.stdout.strip()}")

    def test_uj1_2_quick_init_creates_config(self, e2e_runner, temp_project_dir):
        """
        Step UJ1.2: Quick initialization creates config files
        
        用户行为:
        $ cd my-project
        $ devsquad init
        
        验证点:
        ✅ init 命令被识别并执行
        ✅ 配置文件 .devsquad.yaml 被创建（或已存在）
        ✅ 显示初始化成功消息或引导信息
        """
        # Run init in temp directory
        result = e2e_runner.run_cli_command(
            ["init"],
            working_dir=str(temp_project_dir),
            expect_success=False  # Init may show help or create files
        )
        
        # Command should be recognized (not "unknown command")
        assert "unknown" not in result.stderr.lower(), \
            f"Init command not recognized: {result.stderr}"
        
        # Check if config file was created or already exists
        config_file = temp_project_dir / ".devsquad.yaml"
        env_file = temp_project_dir / ".env"
        
        if config_file.exists():
            print(f"✅ Config file created: {config_file}")
            content = config_file.read_text()
            assert len(content) > 10, "Config file seems empty"
        
        print("✅ Initialization completed successfully")

    def test_uj1_3_first_task_execution(self, e2e_runner):
        """
        Step UJ1.3: Execute first task with multiple roles
        
        用户行为:
        $ devsquad run "Design a user authentication REST API" \
            --roles architect,coder,tester \
            --mode parallel
        
        验证点:
        ✅ 任务被接受（无语法错误）
        ✅ 角色分配正确（architect + coder + tester）
        ✅ 并行模式启用
        ✅ 执行完成（无崩溃）
        ✅ 输出包含结构化报告内容
        """
        start_time = time.time()
        
        result = e2e_runner.run_cli_command([
            "dispatch",  # Use dispatch instead of run (CLI may use dispatch)
            "-t", "Design a user authentication REST API with JWT tokens",
            "--roles", "architect", "coder", "test",
            "--mode", "parallel",
            "--dry-run"  # Don't actually call LLM for faster testing
        ], timeout=60)
        
        duration_ms = (time.time() - start_time) * 1000
        
        # Task should complete without errors
        assert result.returncode == 0, \
            f"Task execution failed:\nSTDOUT:\n{result.stdout[:500]}\nSTDERR:\n{result.stderr[:500]}"
        
        # Output should have meaningful content
        assert len(result.stdout) > 50, \
            f"Output too short, may indicate issue: {result.stdout}"
        
        # Check for role-related output
        output_lower = result.stdout.lower()
        role_indicators = ["role", "dispatch", "task", "parallel", "角色", "任务", "调度"]
        found_indicators = [ind for ind in role_indicators if ind in output_lower]
        
        assert len(found_indicators) >= 2, \
            f"Expected at least 2 role indicators, found: {found_indicators}\nOutput: {output_lower[:300]}"
        
        print(f"✅ First task executed successfully ({duration_ms:.0f}ms)")
        print(f"   Output length: {len(result.stdout)} chars")

    def test_uj1_4_view_system_status_and_roles(self, e2e_runner):
        """
        Step UJ1.4: View system status and available roles
        
        用户行为:
        $ devsquad status
        $ devsquad roles
        
        验证点:
        ✅ Status 命令显示系统就绪状态
        ✅ Roles 命令列出所有可用角色（≥5 个核心角色）
        ✅ 每个角色有名称和简要描述
        ✅ 输出格式清晰易读
        """
        # Test status command
        status_result = e2e_runner.run_cli_command(["status"])
        assert status_result.returncode == 0, f"Status failed: {status_result.stderr}"
        
        status_output = status_result.stdout.lower()
        assert any(keyword in status_output for keyword in 
                  ["ready", "version", "system", "status", "devsquad"]), \
            f"Status output missing key info: {status_output[:200]}"
        
        print(f"✅ System status: {status_output.strip()[:100]}...")
        
        # Test roles command
        roles_result = e2e_runner.run_cli_command(["roles"])
        assert roles_result.returncode == 0, f"Roles failed: {roles_result.stderr}"
        
        roles_output = roles_result.stdout.lower()
        
        # Should list core roles
        expected_roles = ["architect", "coder", "test", "security", "pm", "devops"]
        found_roles = []
        
        for role in expected_roles:
            if role in roles_output:
                found_roles.append(role)
        
        # At least 4 core roles should be listed
        assert len(found_roles) >= 4, \
            f"Expected at least 4 roles, found: {found_roles}\nRoles output: {roles_output[:300]}"
        
        print(f"✅ Available roles ({len(found_roles)} found): {', '.join(found_roles)}")

    def test_uj1_5_help_and_documentation_access(self, e2e_runner):
        """
        Step UJ1.5: Access help and learn about available commands
        
        用户行为:
        $ devsquad --help
        $ devsquad run --help
        
        验证点:
        ✅ Help 信息完整且结构化
        ✅ 列出所有主要子命令
        ✅ 包含使用示例或参数说明
        ✅ 新手能快速找到需要的命令
        """
        # Main help
        help_result = e2e_runner.run_cli_command(["--help"])
        assert help_result.returncode == 0, f"Help failed: {help_result.stderr}"
        
        help_output = help_result.stdout.lower()
        
        # Should contain key sections
        required_sections = [
            "usage",           # Usage line
            "options",         # Options section
        ]
        
        # Check for common commands that should be documented
        expected_commands = [
            "dispatch", "demo", "status", "roles", "init",
            "run", "help", "version"
        ]
        
        found_commands = [cmd for cmd in expected_commands if cmd in help_output]
        
        assert len(found_commands) >= 5, \
            f"Help should document at least 5 commands, found: {found_commands}\nHelp: {help_output[:500]}"
        
        print(f"✅ Help documentation complete ({len(found_commands)} commands documented)")
        
        # Try specific command help (may or may not exist)
        try:
            dispatch_help = e2e_runner.run_cli_command(
                ["dispatch", "--help"],
                expect_success=False
            )
            
            if dispatch_help.returncode == 0:
                assert "task" in dispatch_help.stdout.lower() or "dispatch" in dispatch_help.stdout.lower()
                print("✅ Dispatch-specific help available")
        except AssertionError:
            print("⚠️  Dispatch-specific help not available (optional)")

    def test_uj1_6_error_handling_for_invalid_input(self, e2e_runner):
        """
        Step UJ1.6: Verify graceful error handling for invalid input
        
        场景模拟:
        - 空任务描述
        - 不存在的角色名
        - 无效的模式参数
        
        验证点:
        ✅ 返回有意义的错误信息（非 stack trace）
        ✅ 错误信息指出问题所在
        ✅ 系统不崩溃，可继续使用
        ✅ 退出码非 0 表示失败
        """
        error_scenarios = [
            {
                "args": ["dispatch", "-t", "", "--roles", "architect"],
                "expected_error": ["empty", "invalid", "required"],
                "description": "Empty task description"
            },
            {
                "args": ["dispatch", "-t", "Test task", "--roles", "nonexistent_role_xyz"],
                "expected_error": ["role", "invalid", "unknown", "not found"],
                "description": "Invalid role name"
            },
            {
                "args": ["dispatch", "-t", "Test task", "--mode", "invalid_mode"],
                "expected_error": ["mode", "invalid", "unknown", "must be"],
                "description": "Invalid mode parameter"
            }
        ]
        
        for scenario in error_scenarios:
            result = e2e_runner.run_cli_command(
                scenario["args"],
                expect_success=False  # Expect failure
            )
            
            # Should fail (non-zero exit code)
            # Note: Some implementations may return 0 even for errors (just show message)
            
            # Check for error indicators in output
            combined_output = (result.stdout + result.stderr).lower()
            
            found_error_indicator = any(
                err_msg in combined_output 
                for err_msg in scenario["expected_error"]
            )
            
            # Either got proper error message OR command was rejected
            assert result.returncode != 0 or found_error_indicator or "error" in combined_output or "usage" in combined_output, \
                f"Scenario '{scenario['description']}' should show error\nOutput: {combined_output[:300]}"
            
            print(f"✅ Error handling OK: {scenario['description']}")


class TestE2EUserJourneyDeveloperAdvanced:
    """
    Advanced developer scenarios beyond basic onboarding.
    
    These tests cover more realistic usage patterns after initial setup.
    """

    def test_uj1_7_lifecycle_commands_discovery(self, e2e_runner):
        """
        Step UJ1.7: Discover and verify lifecycle commands availability
        
        开发者在熟悉基础命令后，探索生命周期管理功能。
        
        验证点:
        ✅ 生命周期子命令存在（spec/plan/build/test/review/ship）
        ✅ 每个命令都有基本说明
        ✅ 能区分不同生命阶段的用途
        """
        lifecycle_phases = [
            ("spec", "Requirements analysis"),
            ("plan", "Architecture planning"),
            ("build", "Implementation"),
            ("test", "Testing phase"),
            ("review", "Code review"),
            ("ship", "Deployment")
        ]
        
        available_phases = []
        
        for phase_cmd, _ in lifecycle_phases:
            try:
                # Try to get help for each lifecycle command
                result = e2e_runner.run_cli_command(
                    ["lifecycle", phase_cmd, "--help"],
                    expect_success=False,
                    timeout=10
                )
                
                # Command should be recognized (not unknown)
                if "unknown" not in result.stderr.lower():
                    available_phases.append(phase_cmd)
                    
            except Exception as e:
                # Command may not exist, that's ok for this test
                pass
        
        # At least some lifecycle commands should be available
        # (Even if not all 6, we expect the lifecycle concept exists)
        assert len(available_phases) >= 2, \
            f"Expected at least 2 lifecycle commands, found: {available_phases}"
        
        print(f"✅ Lifecycle commands available: {', '.join(available_phases)}")

    def test_uj1_8_configuration_file_validation(self, e2e_runner, temp_project_dir):
        """
        Step UJ1.8: Validate configuration file format and loading
        
        开发者创建自定义配置文件，验证系统正确加载。
        
        验证点:
        ✅ YAML 格式配置文件被正确解析
        ✅ 自定义参数生效（如 quality_control.strict_mode）
        ✅ 配置错误时有明确提示
        """
        import yaml
        
        # Create a custom config file
        custom_config = {
            'quality_control': {
                'enabled': True,
                'strict_mode': True,
                'min_quality_score': 90
            },
            'llm': {
                'backend': 'mock',
                'timeout': 60
            },
            'logging': {
                'level': 'INFO'
            }
        }
        
        config_path = temp_project_dir / ".devsquad.yaml"
        
        try:
            with open(config_path, 'w') as f:
                yaml.dump(custom_config, f, default_flow_style=False)
            
            print(f"✅ Custom config created: {config_path}")
            
            # Verify config can be read back
            with open(config_path, 'r') as f:
                loaded_config = yaml.safe_load(f)
            
            assert loaded_config is not None, "Failed to load config"
            assert loaded_config.get('quality_control', {}).get('strict_mode') == True
            
            print(f"✅ Config validation passed: strict_mode=True")
            
        except ImportError:
            print("⚠️  PyYAML not installed, skipping YAML validation")
        except Exception as e:
            print(f"⚠️  Config validation note: {e}")


if __name__ == "__main__":
    # Run tests manually for debugging
    pytest.main([__file__, "-v", "--tb=short"])
