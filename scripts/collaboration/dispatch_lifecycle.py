"""Dispatch step → Lifecycle phase mapping.

Maps the 20-step dispatch pipeline to the canonical lifecycle phases
(P0-P11) defined by ``workflow_engine_base.PHASE_TEMPLATES``.
"""

DISPATCH_LIFECYCLE_MAPPING = {
    "step0_tenant_setup": "P1",
    "step1_language": "P1",
    "step2_validation": "P1",
    "step3_rules": "P2",
    "step4_intent": "P1",
    "step5_role_match": "P3",
    "step6_security": "P6",
    "step7_preparation": "P8",
    "step8_execute": "P8",
    "step9_post_exec": "P8",
    "step10_consensus": "P8",
    "step11_permission": "P6",
    "step12_memory": "P11",
    "step13_skillify": "P11",
    "step14_five_axis": "P8",
    "step15_retrospective": "P11",
    "step16_assemble": "P10",
    "step17_hooks": "P10",
    "step18_feedback": "P11",
    "step19_ue_testing": "P9",
    "step20_tech_debt": "P11",
}

# Semantic label for each canonical phase used by the dispatch mapping.
DISPATCH_STAGE_LABELS = {
    "P1": "requirements",
    "P2": "architecture",
    "P3": "technical_design",
    "P6": "security_review",
    "P8": "implementation",
    "P9": "test_execution",
    "P10": "deployment",
    "P11": "operations",
}
