# P0 Feasibility Gate Resolution

## Problem Statement

P0 (Discovery & Feasibility) phase has a logical contradiction:

- **Status**: Optional (`optional: True`)
- **Exit Gate**: "Business case and feasibility confirmed, go decision recorded"

**Contradiction**: If P0 is skipped, how do后续阶段 prove feasibility has been confirmed?

## Root Cause Analysis

This inconsistency exists because P0 was designed to be optional for:
1. Small tasks with self-evident feasibility
2. Iterative enhancements with previously confirmed feasibility
3. Emergency fixes where feasibility assessment would slow response

However, skipping P0 creates a **feasibility proof gap** for subsequent phases.

## Solution Options

### Option A: Make P0 Conditional with Fallback (Recommended)

**Design**:
- P0 remains optional in `PHASE_TEMPLATES`
- P1 (Requirements Analysis) entry gate checks for feasibility proof:
  - If P0 completed → use P0 exit record
  - If P0 skipped → require "feasibility waiver" record in P1 entry

**Implementation**:
```python
# In workflow_engine_base.py PHASE_TEMPLATES
"P1": {
    "name": "Requirements Analysis",
    "gate_condition": "Acceptance criteria quantifiable AND (P0 completed OR feasibility waiver recorded)",
    # ... rest of definition
}
```

**Pros**:
- Preserves P0 optionality
- Closes feasibility proof gap
- Backward compatible (existing P0-skipping workflows add waiver step)

**Cons**:
- Adds complexity to P1 entry logic

### Option B: Make P0 Required

**Design**:
- Change `P0["optional"]` from `True` to `False`
- All workflows must complete P0 before P1

**Pros**:
- Simplest solution
- No feasibility proof gap
- Enforces discipline

**Cons**:
- Breaking change for existing workflows
- Slows emergency response flows
- May be overkill for trivial enhancements

### Option C: Split P0 into Mandatory Core + Optional Extensions

**Design**:
- P0-Core (mandatory): Minimal feasibility assertion (5min)
  - Exit gate: "Feasibility assertion recorded (accept/defer/reject)"
- P0-Extended (optional): Full business case analysis
  - Exit gate: "Detailed cost/risk/ROI analysis complete"

**Pros**:
- Balances discipline and flexibility
- Core assertion prevents proof gap
- Extended analysis optional for complex projects

**Cons**:
- Requires refactoring P0 definition
- Most complex implementation

## Recommendation: Option A (Conditional with Fallback)

### Rationale
1. **Backward Compatible**: Existing workflows continue with minimal adjustment
2. **Proof Gap Closed**: P1 gate enforces feasibility check
3. **Flexibility Preserved**: Teams can skip P0 if they document waiver
4. **Low Implementation Cost**: Only P1 gate logic changes

### Implementation Plan

#### Step 1: Update P1 Gate Condition
```python
# scripts/collaboration/workflow_engine_base.py
"P1": {
    "name": "Requirements Analysis",
    "gate_condition": (
        "Acceptance criteria quantifiable AND "
        "(P0 exit recorded OR feasibility waiver documented)"
    ),
    # ... rest unchanged
}
```

#### Step 2: Add Waiver Check in Workflow Engine
```python
# scripts/collaboration/workflow_engine_lifecycle.py (hypothetical)
def _check_p1_entry_gate(self, workflow_instance):
    """Check P1 entry prerequisites."""
    p0_completed = workflow_instance.get_phase_status("P0") == "completed"
    
    if p0_completed:
        # P0 was completed, check exit gate
        p0_exit = workflow_instance.get_phase_exit_record("P0")
        if "go decision" not in p0_exit:
            raise PhaseGateError("P0 completed but no go decision recorded")
    else:
        # P0 was skipped, check for feasibility waiver
        waiver = workflow_instance.get_attribute("feasibility_waiver")
        if not waiver:
            raise PhaseGateError(
                "P1 entry requires either P0 completion or feasibility waiver. "
                "To proceed without P0, call: "
                "workflow.record_feasibility_waiver(reason='...')"
            )
        logging.info(f"P0 skipped with waiver: {waiver['reason']}")
    
    return True
```

#### Step 3: Add Waiver Recording API
```python
# scripts/collaboration/models.py (WorkflowInstance or WorkflowTrace)
def record_feasibility_waiver(self, reason: str, approver: str = "system"):
    """Record feasibility waiver when skipping P0.
    
    Args:
        reason: Why P0 is being skipped (e.g., "trivial enhancement", 
                "emergency hotfix", "previously assessed")
        approver: Who approved the waiver (defaults to "system" for self-service)
    """
    self.set_attribute("feasibility_waiver", {
        "reason": reason,
        "approver": approver,
        "timestamp": datetime.now().isoformat()
    })
    logging.info(f"Feasibility waiver recorded: {reason}")
```

### Verification

#### Test Case 1: P0 Completed
```python
workflow = WorkflowInstance(...)
workflow.complete_phase("P0", exit_record="go decision: proceed")
workflow.start_phase("P1")  # Should succeed
```

#### Test Case 2: P0 Skipped with Waiver
```python
workflow = WorkflowInstance(...)
workflow.record_feasibility_waiver(reason="trivial CSS fix")
workflow.start_phase("P1")  # Should succeed
```

#### Test Case 3: P0 Skipped without Waiver (ERROR)
```python
workflow = WorkflowInstance(...)
# No P0, no waiver
workflow.start_phase("P1")  # Should raise PhaseGateError
```

## Migration Path

### For Existing Workflows
1. **No P0 history**: Add one-time waiver via migration script
   ```python
   for workflow in get_all_workflows():
       if not workflow.has_phase("P0"):
           workflow.record_feasibility_waiver(
               reason="Legacy workflow - feasibility pre-confirmed",
               approver="migration-bot"
           )
   ```

2. **Future workflows**: Use waiver API when skipping P0

### Documentation Updates
- Update SKILL.md to explain P0 optionality + waiver requirement
- Add waiver examples to QUICKSTART.md
- Update lifecycle diagram to show P1 entry decision diamond

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Teams misuse waivers | Feasibility gap persists | Add audit report for waiver patterns |
| Legacy workflows break | Migration effort | Provide migration script and grace period |
| Complexity increases | Maintenance burden | Keep waiver logic simple, well-tested |

## Success Criteria

1. ✅ P1 cannot start without feasibility proof or waiver
2. ✅ P0 skipping workflows continue to function
3. ✅ Test coverage for all three scenarios (P0 done, waived, missing)
4. ✅ Documentation updated
5. ✅ Migration script tested on 10+ legacy workflows

## References

- [Workflow Engine Base](../scripts/collaboration/workflow_engine_base.py)
- [Phase Transition Boundary Tests](../tests/unit/test_phase_transition_boundaries.py)
- Original audit finding: P0-3 in review report
