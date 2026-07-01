#!/usr/bin/env python3
"""
Test script for DevSquad configuration injection

This script verifies:
1. Configuration file loading (.devsquad.yaml)
2. Quality control rule building
3. Rule injection into assembled prompts
"""

import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from scripts.collaboration.prompt_assembler import PromptAssembler  # noqa: E402


def test_config_loading():
    """Test 1: Verify configuration file is loaded correctly"""
    print("=" * 60)
    print("TEST 1: Configuration Loading")
    print("=" * 60)

    assembler = PromptAssembler(
        role_id="architect",
        base_prompt="You are a software architect. Design systems with scalability and maintainability in mind.",
    )

    print(f"✓ QC Enabled: {assembler.qc_enabled}")
    print(f"✓ QC Config loaded: {bool(assembler.qc_config)}")

    if assembler.qc_enabled:
        qc = assembler.qc_config.get("quality_control", {})
        print(f"✓ Strict Mode: {qc.get('strict_mode')}")
        print(f"✓ Min Score: {qc.get('min_quality_score')}")

        aqc = qc.get("ai_quality_control", {})
        print(f"✓ AI QC enabled: {aqc.get('enabled')}")
        hc = aqc.get("hallucination_check", {})
        print(f"✓ Hallucination check: {hc.get('enabled')}")

        assert qc.get("strict_mode") is not None, "strict_mode should be set in QC config"
        assert qc.get("min_quality_score") is not None, "min_quality_score should be set in QC config"
    else:
        print("✗ Quality control not enabled - config may not be loaded")
        raise AssertionError("QC config not loaded")


def test_qc_injection_building():
    """Test 2: Verify quality control injection is built correctly"""
    print("\n" + "=" * 60)
    print("TEST 2: Quality Control Injection Building")
    print("=" * 60)

    assembler = PromptAssembler(
        role_id="solo-coder", base_prompt="You are a full-stack developer. Write clean, tested code."
    )

    if assembler.qc_enabled and assembler._qc_injection:
        injection = assembler._qc_injection

        # Check for key sections
        checks = [
            ("Quality Control System header", "Quality Control System (ACTIVE)" in injection),
            ("Hallucination Prevention", "Hallucination Prevention" in injection),
            ("Overconfidence Prevention", "Overconfidence Prevention" in injection),
            ("Security Rules", "Security Rules" in injection),
            ("Collaboration Rules", "Collaboration Rules" in injection),
            ("Output Quality Gate", "Output Quality Gate" in injection),
            ("Strict mode indicator", "Strict Mode: ON" in injection),
        ]

        all_passed = True
        for check_name, result in checks:
            status = "✓" if result else "✗"
            print(f"{status} {check_name}: {'Found' if result else 'Missing'}")
            if not result:
                all_passed = False

        print(f"\nInjection length: {len(injection)} characters")

        assert all_passed, "All QC injection checks should pass"
    else:
        print("✗ QC injection not built - check configuration")
        raise AssertionError("QC injection not built")


def test_prompt_injection():
    """Test 3: Verify rules are injected into final prompts"""
    print("\n" + "=" * 60)
    print("TEST 3: Prompt Injection (Simple Task)")
    print("=" * 60)

    assembler = PromptAssembler(role_id="tester", base_prompt="You are a QA engineer. Write comprehensive tests.")

    # Test with a simple task
    result = assembler.assemble(
        task_description="写一个排序函数的单元测试", related_findings=["发现A: 需要测试边界条件"], task_id="TEST-001"
    )

    instruction = result.instruction

    print(f"Task complexity detected: {result.complexity.value}")
    print(f"Template variant used: {result.variant_used}")
    print(f"Total instruction length: {len(instruction)} characters")

    # Check if QC injection is present
    has_qc = "Quality Control System (ACTIVE)" in instruction
    print(f"\n{'✓' if has_qc else '✗'} QC rules injected in prompt: {has_qc}")

    if has_qc:
        # Show snippet of the injection
        qc_start = instruction.find("## ⚠️ Quality Control System")
        if qc_start != -1:
            snippet = instruction[qc_start : qc_start + 200]
            print(f"\nInjection preview:\n{snippet}...")

    assert has_qc, "QC rules should be injected in prompt"


def test_complex_task_injection():
    """Test 4: Verify injection works for complex tasks too"""
    print("\n" + "=" * 60)
    print("TEST 4: Prompt Injection (Complex Task)")
    print("=" * 60)

    assembler = PromptAssembler(
        role_id="architect", base_prompt="You are a software architect. Design scalable systems."
    )

    # Test with a complex task
    complex_task = """
    设计一个高可用的微服务架构，要求：
    1. 支持水平扩展
    2. 实现服务发现和负载均衡
    3. 包含熔断器和限流机制
    4. 考虑数据一致性方案
    5. 提供监控和告警系统
    """

    result = assembler.assemble(
        task_description=complex_task,
        related_findings=["发现A: 当前单体应用性能瓶颈", "发现B: 业务增长预期10倍", "发现C: 需要99.99%可用性"],
        task_id="ARCH-001",
    )

    instruction = result.instruction

    print(f"Task complexity detected: {result.complexity.value}")
    print(f"Template variant used: {result.variant_used}")
    print(f"Total instruction length: {len(instruction)} characters")

    # Verify QC injection present
    has_qc = "Quality Control System (ACTIVE)" in instruction
    print(f"\n{'✓' if has_qc else '✗'} QC rules injected: {has_qc}")

    # Check for specific rules in complex task
    has_hallucination_check = (
        "references must include" in instruction.lower() or "Hallucination Prevention" in instruction
    )
    has_alternatives = "alternatives" in instruction.lower()
    has_security = "PermissionGuard" in instruction

    print(f"{'✓' if has_hallucination_check else '✗'} Hallucination rules present")
    print(f"{'✓' if has_alternatives else '✗'} Alternatives requirement present")
    print(f"{'✓' if has_security else '✗'} Security rules present")

    assert has_qc, "QC rules should be injected"
    assert has_hallucination_check, "Hallucination rules should be present"
    assert has_alternatives, "Alternatives requirement should be present"


def test_disabled_mode():
    """Test 5: Verify behavior when QC is disabled"""
    print("\n" + "=" * 60)
    print("TEST 5: Disabled Mode (No Config File)")
    print("=" * 60)

    # Create assembler in a directory without .devsquad.yaml
    original_cwd = os.getcwd()
    try:
        os.chdir("/tmp")  # Switch to temp dir (no config)
        assembler = PromptAssembler(role_id="coder", base_prompt="You are a developer.")

        result = assembler.assemble(task_description="写个hello world")
        instruction = result.instruction

        has_no_qc = "Quality Control System" not in instruction
        print(f"{'✓' if has_no_qc else '✗'} No QC injection when disabled: {has_no_qc}")
        print(f"QC enabled flag: {assembler.qc_enabled}")

        assert has_no_qc, "No QC injection when disabled"
    finally:
        os.chdir(original_cwd)


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("DevSquad Configuration Injection Test Suite")
    print("=" * 60)
    print(f"Working directory: {os.getcwd()}")
    print(f"Config file exists: {os.path.exists('.devsquad.yaml')}")

    # Run all tests
    test_config_loading()
    test_qc_injection_building()
    test_prompt_injection()
    test_complex_task_injection()
    test_disabled_mode()

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print("\n🎉 All tests passed! Configuration injection is working correctly.")


if __name__ == "__main__":
    main()
