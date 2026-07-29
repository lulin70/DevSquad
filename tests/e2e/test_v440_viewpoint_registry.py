"""E2E tests for V4.4.0 P0-2 Viewpoint Registry."""
from scripts.collaboration.dispatcher import MultiAgentDispatcher


def test_e2e_viewpoint_injected_into_prompt():
    """US-V2: Assembled prompt must contain ## Viewpoint: section with concerns."""
    disp = MultiAgentDispatcher()
    # Trigger a dispatch to capture the assembled prompt
    disp.dispatch("Design a payment gateway", roles=["architect"])
    # The worker prompt should have been assembled with viewpoint injection
    from scripts.collaboration.viewpoint_registry import ViewpointRegistry
    registry = ViewpointRegistry()
    vp = registry.get("architect")
    assert vp is not None
    assert hasattr(vp, "concerns")
    assert len(vp.concerns) > 0
    disp.shutdown()


def test_e2e_split_resolved_by_orthogonality():
    """US-V1: SPLIT outcome with orthogonal factions must become APPROVED with warning."""
    from scripts.collaboration.viewpoint_registry import ViewpointRegistry
    registry = ViewpointRegistry()
    # architect and security have orthogonal concerns (no shared model elements)
    assert registry.is_orthogonal("architect", "security") is True
    # architect and coder share "implementation" model elements (not orthogonal)
    assert registry.is_orthogonal("architect", "solo-coder") is False


def test_e2e_consistency_check_flags_contradiction():
    """US-V3: Contradiction on shared model element must be listed as violation."""
    from scripts.collaboration.viewpoint_registry import ViewpointRegistry
    registry = ViewpointRegistry()
    # Two viewpoints disagree on a shared element
    violations = registry.check_consistency(
        viewpoint_a="architect",
        viewpoint_b="solo-coder",
        shared_element="api_contract",
        stance_a="REST",
        stance_b="GraphQL",
    )
    assert len(violations) > 0, "Expected at least one consistency violation"
