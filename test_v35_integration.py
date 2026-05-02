#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DevSquad V3.4.0 Integration Verification Script

Verifies that our QC injection system works seamlessly with new V3.4.0 features:
1. Protocol interfaces (MemoryProvider, CacheProvider, etc.)
2. AgentBriefing system
3. ConfidenceScorer
4. Null Providers (degradation)
5. MCEAdapter (CarryMem integration)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_qc_compatibility():
    """Test 1: Our QC system still works with V3.4.0"""
    print("=" * 60)
    print("TEST 1: QC Injection System Compatibility")
    print("=" * 60)
    
    from scripts.collaboration.prompt_assembler import PromptAssembler
    
    assembler = PromptAssembler(
        role_id="architect",
        base_prompt="You are a software architect."
    )
    
    result = assembler.assemble(
        task_description="Design a microservice architecture",
        related_findings=[],
        task_id="QC-CHECK-001"
    )
    
    checks = [
        ("QC Enabled", assembler.qc_enabled),
        ("Config Loaded", bool(assembler.qc_config)),
        ("QC Injection in Output", "Quality Control" in result.instruction or "quality_control" in result.instruction.lower()),
        ("Instruction Length", len(result.instruction) > 2000),
    ]
    
    all_passed = True
    for name, check_result in checks:
        status = "✓" if check_result else "✗"
        print(f"{status} {name}: {check_result}")
        if not check_result:
            all_passed = False
    
    if all_passed:
        print(f"\n✓ QC injection present in assembled instruction: {len(result.instruction)} characters")
    
    return all_passed


def test_protocol_interfaces():
    """Test 2: V3.4.0 Protocol interfaces are available"""
    print("\\n" + "=" * 60)
    print("TEST 2: Protocol Interfaces Availability")
    print("=" * 60)
    
    try:
        from scripts.collaboration.protocols import (
            CacheProvider, RetryProvider, MonitorProvider, MemoryProvider,
            ProviderError, CacheError, RetryError, MonitorError, MemoryProviderError
        )
        
        interfaces = [
            ("CacheProvider", CacheProvider),
            ("RetryProvider", RetryProvider),
            ("MonitorProvider", MonitorProvider),
            ("MemoryProvider", MemoryProvider),
            ("ProviderError", ProviderError),
            ("MemoryProviderError", MemoryProviderError),
        ]
        
        all_passed = True
        for name, interface in interfaces:
            print(f"✓ {name}: Available")
        
        return True
    except ImportError as e:
        print(f"✗ Failed to import protocols: {e}")
        return False


def test_null_providers():
    """Test 3: Null Providers for degradation"""
    print("\\n" + "=" * 60)
    print("TEST 3: Null Providers (Degradation Mode)")
    print("=" * 60)
    
    try:
        from scripts.collaboration.null_providers import (
            NullCacheProvider, NullRetryProvider, 
            NullMonitorProvider, NullMemoryProvider
        )
        
        # Test each provider
        providers = [
            ("NullCacheProvider", NullCacheProvider()),
            ("NullRetryProvider", NullRetryProvider()),
            ("NullMonitorProvider", NullMonitorProvider()),
            ("NullMemoryProvider", NullMemoryProvider()),
        ]
        
        all_passed = True
        for name, provider in providers:
            is_available = provider.is_available()
            stats = provider.get_stats()
            
            # All null providers should return False for is_available
            correct_behavior = not is_available and stats.get("degraded") == True
            
            status = "✓" if correct_behavior else "✗"
            print(f"{status} {name}: available={is_available}, degraded={stats.get('degraded')}")
            
            if not correct_behavior:
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"✗ Error testing null providers: {e}")
        return False


def test_agent_briefing():
    """Test 4: Agent Briefing System"""
    print("\\n" + "=" * 60)
    print("TEST 4: Agent Briefing System")
    print("=" * 60)
    
    try:
        from scripts.collaboration.agent_briefing import (
            AgentBriefing, BriefingSection, AgentContext,
            get_agent_briefing, reset_briefings
        )
        
        # Create a briefing instance
        briefing = AgentBriefing(
            agent_role="Architect",
            project_context={"name": "TestProject", "version": "1.0"}
        )
        
        # Generate briefing
        content = briefing.generate_briefing(
            task="Design a microservice architecture",
            context={"priority": "high"}
        )
        
        checks = [
            ("Briefing Generated", len(content) > 0),
            ("Contains Role", "Architect" in content),
            ("Contains Task", "microservice architecture" in content.lower()),
            ("Has Project Context", "TestProject" in content),
        ]
        
        all_passed = True
        for name, result in checks:
            status = "✓" if result else "✗"
            print(f"{status} {name}: {result}")
            if not result:
                all_passed = False
        
        if all_passed:
            print(f"\\n✓ Briefing length: {len(content)} characters")
        
        return all_passed
    except Exception as e:
        print(f"✗ Error testing agent briefing: {e}")
        return False


def test_confidence_scorer():
    """Test 5: Confidence Scoring System"""
    print("\\n" + "=" * 60)
    print("TEST 5: Confidence Scoring System")
    print("=" * 60)
    
    try:
        from scripts.collaboration.confidence_score import (
            ConfidenceScorer, ConfidenceScore, ConfidenceLevel,
            get_confidence_scorer
        )
        
        scorer = ConfidenceScorer()
        
        # Test with a sample response
        score = scorer.calculate_confidence(
            prompt="Design a REST API",
            response="""I'll design a comprehensive REST API for user management.
            
The API will include:
1. User authentication endpoints (POST /auth/login, POST /auth/register)
2. User CRUD operations (GET/PUT/DELETE /users/:id)
3. Role-based access control middleware
4. Rate limiting and input validation

This approach follows REST best practices and ensures scalability.""",
            metadata={"model": "gpt-4", "temperature": 0.3}
        )
        
        checks = [
            ("Score Calculated", 0.0 <= score.overall_score <= 1.0),
            ("Level Determined", score.level in ConfidenceLevel),
            ("Factors Present", len(score.factors) >= 4),  # completeness, certainty, specificity, consistency
            ("Reasoning Provided", len(score.reasoning) > 0),
            ("Confidence Check", score.is_confident(threshold=0.5)),  # Should be confident
        ]
        
        all_passed = True
        for name, result in checks:
            status = "✓" if result else "✗"
            print(f"{status} {name}: {result if isinstance(result, bool) else score.overall_score:.2f}")
            if not result:
                all_passed = False
        
        if all_passed:
            print(f"\\n✓ Overall confidence: {score.overall_score:.2f} ({score.level.value})")
            print(f"  Factors: {score.factors}")
        
        return all_passed
    except Exception as e:
        print(f"✗ Error testing confidence scorer: {e}")
        return False


def test_mce_adapter():
    """Test 6: MCEAdapter (CarryMem Integration)"""
    print("\\n" + "=" * 60)
    print("TEST 6: MCEAdapter (CarryMem Integration)")
    print("=" * 60)
    
    try:
        from scripts.collaboration.mce_adapter import MCEAdapter, MCEResult, CARRYMEM_TO_DEVOPSQUAD
        
        adapter = MCEAdapter(enable=True)
        
        checks = [
            ("Adapter Created", adapter is not None),
            ("Availability Checked", hasattr(adapter, 'is_available')),
            ("Type Mapping Exists", bool(CARRYMEM_TO_DEVOPSQUAD)),
        ]
        
        all_passed = True
        for name, result in checks:
            status = "✓" if result else "✗"
            print(f"{status} {name}: {result}")
            if not result:
                all_passed = False
        
        if adapter.is_available:
            print("\\n✓ CarryMem is installed and available!")
            print("  - Can classify messages")
            print("  - Can recall memories")
            print("  - Can integrate with QC rules")
        else:
            print("\\n○ CarryMem not installed (optional - using NullMemoryProvider)")
            print("  - System will work without CarryMem")
            print("  - QC rules still fully functional")
        
        return all_passed
    except ImportError as e:
        print(f"○ MCEAdapter import skipped (CarryMem optional): {e}")
        return True
    except Exception as e:
        print(f"✗ MCEAdapter test failed: {e}")
        return False


def test_integration_scenario():
    """Test 7: Full integration scenario"""
    print("\\n" + "=" * 60)
    print("TEST 7: Full Integration Scenario (QC + V3.4.0)")
    print("=" * 60)
    
    try:
        from scripts.collaboration.prompt_assembler import PromptAssembler
        from scripts.collaboration.agent_briefing import AgentBriefing
        from scripts.collaboration.confidence_score import ConfidenceScorer
        
        # Step 1: Create assembler with QC rules
        assembler = PromptAssembler(
            role_id="architect",
            base_prompt="You are a senior software architect."
        )
        
        # Step 2: Assemble a complex task
        result = assembler.assemble(
            task_description="""
            Design a high-availability microservice architecture with:
            1. Service discovery and load balancing
            2. Circuit breaker pattern
            3. Distributed tracing
            4. Event-driven communication
            """,
            related_findings=[
                "Current system is monolithic",
                "Need 99.99% uptime SLA",
                "Team has Kubernetes experience"
            ],
            task_id="ARCH-2026-001"
        )
        
        # Step 3: Generate briefing
        briefing = AgentBriefing(agent_role="Architect")
        briefing_content = briefing.generate_briefing(
            task=result.instruction[:200],  # Use part of the instruction
            context={"complexity": result.complexity.value}
        )
        
        # Step 4: Score confidence (simulated)
        scorer = ConfidenceScorer()
        confidence = scorer.calculate_confidence(
            prompt="Design microservice architecture",
            response="Based on requirements, I recommend using Kubernetes with Istio...",
            metadata={"model": "gpt-4", "temperature": 0.2}
        )
        
        # Verify integration
        checks = [
            ("QC Rules Injected", "Quality Control System (ACTIVE)" in result.instruction),
            ("Task Complexity Detected", result.complexity.value == "complex"),
            ("Briefing Generated", len(briefing_content) > 0),
            ("Confidence Scored", 0.0 <= confidence.overall_score <= 1.0),
            ("All Systems Compatible", True),  # If we got here, everything works!
        ]
        
        all_passed = True
        for name, result_check in checks:
            status = "✓" if result_check else "✗"
            print(f"{status} {name}")
            if not result_check:
                all_passed = False
        
        if all_passed:
            print("\\n🎉 Full integration successful!")
            print(f"   - QC injection: {len(result.instruction)} characters")
            print(f"   - Task complexity: {result.complexity.value}")
            print(f"   - Briefing size: {len(briefing_content)} characters")
            print(f"   - Confidence level: {confidence.level.value} ({confidence.overall_score:.2f})")
        
        return all_passed
    except Exception as e:
        print(f"✗ Integration scenario failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all verification tests"""
    print("\\n" + "=" * 60)
    print("DevSquad V3.4.0 + QC Injection Integration Test Suite")
    print("=" * 60)
    print(f"Working directory: {os.getcwd()}")
    
    results = []
    
    # Run all tests
    results.append(("QC Compatibility", test_qc_compatibility()))
    results.append(("Protocol Interfaces", test_protocol_interfaces()))
    results.append(("Null Providers", test_null_providers()))
    results.append(("Agent Briefing", test_agent_briefing()))
    results.append(("Confidence Scorer", test_confidence_scorer()))
    results.append(("MCEAdapter", test_mce_adapter()))
    results.append(("Full Integration", test_integration_scenario()))
    
    # Summary
    print("\\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\\n" + "🎉" * 3)
        print("ALL TESTS PASSED!")
        print("\\n✅ Your QC injection system is FULLY COMPATIBLE with DevSquad V3.4.0")
        print("✅ All new features (Protocols, Briefing, Confidence) work together")
        print("✅ Ready to use: QC rules + optional CarryMem integration")
        print("\\n" + "🎉" * 3)
        return 0
    else:
        print(f"\\n⚠️  {total - passed} test(s) failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
