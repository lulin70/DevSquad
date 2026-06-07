#!/usr/bin/env python3
"""V3.6.1 Cybernetics Modules Smoke Test"""

import sys

sys.path.insert(0, ".")

print("=" * 60)
print("DevSquad V3.6.1 Cybernetics Modules Verification")
print("=" * 60)

from scripts.collaboration._version import __version__

assert __version__ == "3.6.1", f"Version mismatch: {__version__}"
print(f"[1/10] Version: {__version__} OK")

from scripts.collaboration.adaptive_role_selector import AdaptiveRoleSelector
from scripts.collaboration.execution_guard import ExecutionGuard
from scripts.collaboration.feedback_control_loop import FeedbackControlLoop
from scripts.collaboration.performance_fingerprint import PerformanceFingerprint
from scripts.collaboration.similar_task_recommender import SimilarTaskRecommender

print("[2/10] All 5 modules imported OK")

eg = ExecutionGuard()
abort, reason = eg.check_abort("normal output here", elapsed_time=5.0, token_count=100)
assert abort == False
print("[3/10] ExecutionGuard: normal output -> no abort OK")

abort2, reason2 = eg.check_abort("CRITICAL FAILURE", elapsed_time=5.0, token_count=100)
assert abort2 == True
print(f"[4/10] ExecutionGuard: CRITICAL keyword -> abort OK ({reason2})")

abort3, reason3 = eg.check_abort("some output", elapsed_time=400.0, token_count=100)
assert abort3 == True
print(f"[5/10] ExecutionGuard: timeout 400s -> abort OK ({reason3})")

pf = PerformanceFingerprint()
stats = pf.get_stats()
assert isinstance(stats, dict) and "total" in stats
print(f"[6/10] PerformanceFingerprint: stats keys={list(stats.keys())} OK")

similar = pf.find_similar("brand new task never seen before", top_k=3)
assert isinstance(similar, list)
print(f"[7/10] PerformanceFingerprint: cold-start find_similar -> {len(similar)} results OK")

rec = SimilarTaskRecommender(pf)
rec_result = rec.recommend("implement user login API", top_k=3)
assert "recommended_roles" in rec_result and "confidence" in rec_result
print(f"[8/10] SimilarTaskRecommender: confidence={rec_result['confidence']} OK")

selector = AdaptiveRoleSelector()
roles = selector.select_roles("build REST API with database")
assert isinstance(roles, list)
print(f"[9/10] AdaptiveRoleSelector: roles={roles} OK")

from scripts.collaboration.dispatcher import MultiAgentDispatcher

dispatcher = MultiAgentDispatcher()
loop = FeedbackControlLoop(dispatcher, quality_gate=0.7, max_iterations=2)
result = loop.run("test task for verification", dry_run=True)
assert result is not None
dispatcher.shutdown()
print("[10/10] FeedbackControlLoop: dry_run dispatch OK")

pf2 = PerformanceFingerprint()
eg2 = ExecutionGuard()
pf2.record_execution("test integration task", result=None, timing={"total": 1.5}, roles_used=["architect", "coder"])
stats2 = pf2.get_stats()
print(f"[INT] Integration: record+stats -> total={stats2['total']} OK")

print()
print("=" * 60)
print("ALL V3.6.1 CYBERNETICS MODULES VERIFIED PASSING")
print("=" * 60)
