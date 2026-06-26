"""Dispatch step → Lifecycle phase mapping.

Maps the 20-step dispatch pipeline to the 11-phase lifecycle (P1-P11).
"""

DISPATCH_LIFECYCLE_MAPPING = {
    "step0_tenant_setup": "P1_Requirements",
    "step1_language": "P1_Requirements",
    "step2_validation": "P1_Requirements",
    "step3_rules": "P2_Architecture",
    "step4_intent": "P2_Architecture",
    "step5_role_match": "P3_Implementation",
    "step6_security": "P6_Security",
    "step7_preparation": "P3_Implementation",
    "step8_execute": "P3_Implementation",
    "step9_post_exec": "P4_Review",
    "step10_consensus": "P4_Review",
    "step11_permission": "P6_Security",
    "step12_memory": "P5_Integration",
    "step13_skillify": "P8_Optimization",
    "step14_five_axis": "P4_Review",
    "step15_retrospective": "P9_Retrospective",
    "step16_assemble": "P10_Delivery",
    "step17_hooks": "P10_Delivery",
    "step18_feedback": "P11_Monitoring",
    "step19_ue_testing": "P7_TestPlanning",
    "step20_tech_debt": "P9_TestExecution",
}
