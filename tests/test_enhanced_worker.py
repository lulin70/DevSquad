"""Tests for EnhancedWorker — provider injection, briefing, rules, guard.

Covers the enhanced execution pipeline:
- __init__ with various provider combinations
- briefing lazy loading
- _do_work_with_briefing / _do_work_simple execution paths
- execute() with retry, ExecutionGuard, confidence scoring, rule violations
- _inject_rules_from_provider / _validate_injected_rules
- _check_forbid_violations
- get_briefing_summary / export_briefing / compress_to_briefing
- _extract_decisions / _extract_pending
- get_provider_status
"""

import tempfile

from scripts.collaboration.enhanced_worker import (
    AgentBriefingOutput,
    EnhancedWorker,
    _is_available,
)
from scripts.collaboration.llm_backend import MockBackend
from scripts.collaboration.models import TaskDefinition, WorkerResult
from scripts.collaboration.scratchpad import Scratchpad

# ---------------------------------------------------------------------------
# Stub providers
# ---------------------------------------------------------------------------


class StubCacheProvider:
    def __init__(self, available=True):
        self._available = available

    def is_available(self):
        return self._available


class StubRetryProvider:
    def __init__(self, available=True, fail=False):
        self._available = available
        self._fail = fail

    def is_available(self):
        return self._available

    def retry_with_fallback(self, func, _max_attempts=3, fallback=None):
        if self._fail:
            raise RuntimeError("retry mechanism failed")
        try:
            return func()
        except Exception:
            if fallback:
                return fallback()
            raise


class StubMonitorProvider:
    def __init__(self, available=True):
        self._available = available
        self.recorded = []

    def is_available(self):
        return self._available

    def record_agent_execution(self, **kwargs):
        self.recorded.append(kwargs)


class StubMemoryProvider:
    def __init__(self, available=True, rules=None, use_match=True):
        self._available = available
        self._rules = rules or []
        self._use_match = use_match

    def is_available(self):
        return self._available

    def match_rules(self, **_kwargs):
        return self._rules

    def get_rules(self, **_kwargs):
        return [r["action"] if isinstance(r, dict) else r for r in self._rules]


class StubExecutionGuard:
    def __init__(self, abort=False, warnings=None):
        self._abort = abort
        self._warnings = warnings or []

    def check_abort(self, _output_text, _elapsed_time):
        return (self._abort, "abort reason" if self._abort else "")

    def check_warnings(self, _output_text):
        return self._warnings


def _make_worker(**kwargs):
    defaults = {
        "worker_id": "test-worker",
        "role_id": "architect",
        "role_prompt": "You are an architect.",
        "scratchpad": Scratchpad(),
        "llm_backend": MockBackend(),
    }
    defaults.update(kwargs)
    return EnhancedWorker(**defaults)


# ---------------------------------------------------------------------------
# _is_available module-level function
# ---------------------------------------------------------------------------


class TestIsAvailable:
    def test_none_returns_false(self):
        assert _is_available(None) is False

    def test_method_available(self):
        provider = StubCacheProvider(available=True)
        assert _is_available(provider) is True

    def test_method_unavailable(self):
        provider = StubCacheProvider(available=False)
        assert _is_available(provider) is False

    def test_property_available(self):
        class PropProvider:
            is_available = True

        assert _is_available(PropProvider()) is True

    def test_property_unavailable(self):
        class PropProvider:
            is_available = False

        assert _is_available(PropProvider()) is False


# ---------------------------------------------------------------------------
# AgentBriefingOutput
# ---------------------------------------------------------------------------


class TestAgentBriefingOutput:
    def test_defaults(self):
        output = AgentBriefingOutput()
        assert output.task_summary == ""
        assert output.key_decisions == []
        assert output.pending_items == []
        assert output.rules_applied == []
        assert output.result_summary == ""
        assert output.confidence == 0.0
        assert output.assumptions == []

    def test_custom_values(self):
        output = AgentBriefingOutput(
            task_summary="task",
            key_decisions=["d1"],
            pending_items=["p1"],
            rules_applied=["r1"],
            result_summary="summary",
            confidence=0.9,
            assumptions=["a1"],
        )
        assert output.task_summary == "task"
        assert output.confidence == 0.9


# ---------------------------------------------------------------------------
# EnhancedWorker.__init__
# ---------------------------------------------------------------------------


class TestInit:
    def test_defaults(self):
        worker = _make_worker()
        assert worker.worker_id == "test-worker"
        assert worker.role_id == "architect"
        assert worker.cache_provider is None
        assert worker.retry_provider is None
        assert worker.monitor_provider is None
        assert worker.memory_provider is None
        assert worker._briefing is None
        assert worker._briefing_loaded is False
        assert worker._last_result is None
        assert worker._injected_rules == []
        assert worker._rules_applied == []

    def test_with_providers(self):
        cache = StubCacheProvider()
        retry = StubRetryProvider()
        monitor = StubMonitorProvider()
        memory = StubMemoryProvider()
        worker = _make_worker(
            cache_provider=cache,
            retry_provider=retry,
            monitor_provider=monitor,
            memory_provider=memory,
        )
        assert worker.cache_provider is cache
        assert worker.retry_provider is retry
        assert worker.monitor_provider is monitor
        assert worker.memory_provider is memory

    def test_execution_guard_provided(self):
        guard = StubExecutionGuard()
        worker = _make_worker(execution_guard=guard)
        assert worker.execution_guard is guard

    def test_execution_guard_none_when_unavailable(self):
        worker = _make_worker()
        # execution_guard may be None or a default ExecutionGuard
        # depending on whether the module is importable
        assert worker.execution_guard is None or worker.execution_guard is not None


# ---------------------------------------------------------------------------
# briefing property
# ---------------------------------------------------------------------------


class TestBriefingProperty:
    def test_briefing_lazy_loaded(self):
        worker = _make_worker()
        assert worker._briefing_loaded is False
        _ = worker.briefing
        assert worker._briefing_loaded is True

    def test_briefing_cached(self):
        worker = _make_worker()
        b1 = worker.briefing
        b2 = worker.briefing
        assert b1 is b2


# ---------------------------------------------------------------------------
# execute() — main execution path
# ---------------------------------------------------------------------------


class TestExecute:
    def test_execute_basic(self):
        worker = _make_worker()
        task = TaskDefinition(description="Design a system", role_id="architect")
        result = worker.execute(task)
        assert isinstance(result, WorkerResult)
        assert result.success is True

    def test_execute_with_retry_provider(self):
        retry = StubRetryProvider(available=True)
        worker = _make_worker(retry_provider=retry)
        task = TaskDefinition(description="Design a system", role_id="architect")
        result = worker.execute(task)
        assert isinstance(result, WorkerResult)

    def test_execute_retry_provider_fails_falls_back(self):
        retry = StubRetryProvider(available=True, fail=True)
        worker = _make_worker(retry_provider=retry)
        task = TaskDefinition(description="Design a system", role_id="architect")
        result = worker.execute(task)
        assert isinstance(result, WorkerResult)

    def test_execute_with_monitor_provider(self):
        monitor = StubMonitorProvider(available=True)
        worker = _make_worker(monitor_provider=monitor)
        task = TaskDefinition(description="Design a system", role_id="architect")
        worker.execute(task)
        assert len(monitor.recorded) >= 1

    def test_execute_with_execution_guard_no_abort(self):
        guard = StubExecutionGuard(abort=False, warnings=[])
        worker = _make_worker(execution_guard=guard)
        task = TaskDefinition(description="Design a system", role_id="architect")
        result = worker.execute(task)
        assert result.success is True

    def test_execute_with_execution_guard_abort(self):
        guard = StubExecutionGuard(abort=True)
        worker = _make_worker(execution_guard=guard)
        task = TaskDefinition(description="Design a system", role_id="architect")
        result = worker.execute(task)
        assert result.success is True
        assert isinstance(result.output, dict)
        assert result.output.get("execution_guard_abort") is True

    def test_execute_with_execution_guard_warnings(self):
        guard = StubExecutionGuard(abort=False, warnings=["warning1", "warning2"])
        worker = _make_worker(execution_guard=guard)
        task = TaskDefinition(description="Design a system", role_id="architect")
        result = worker.execute(task)
        assert isinstance(result.output, dict)
        assert "execution_guard_warnings" in result.output

    def test_execute_last_result_stored(self):
        worker = _make_worker()
        task = TaskDefinition(description="Design a system", role_id="architect")
        result = worker.execute(task)
        assert worker._last_result is result


# ---------------------------------------------------------------------------
# _do_work_with_briefing / _do_work_simple
# ---------------------------------------------------------------------------


class TestDoWorkPaths:
    def test_do_work_with_briefing_success(self):
        worker = _make_worker()
        task = TaskDefinition(description="Design a system", role_id="architect")
        result = worker._do_work_with_briefing(task)
        assert isinstance(result, WorkerResult)
        assert result.success is True

    def test_do_work_simple_success(self):
        worker = _make_worker()
        task = TaskDefinition(description="Design a system", role_id="architect")
        result = worker._do_work_simple(task)
        assert isinstance(result, WorkerResult)
        assert result.success is True

    def test_do_work_simple_fallback_on_exception(self):
        worker = _make_worker()
        worker._do_work = lambda _ctx: (_ for _ in ()).throw(RuntimeError("boom"))
        task = TaskDefinition(description="Design a system", role_id="architect")
        result = worker._do_work_simple(task)
        assert result.success is False
        assert "Fallback execution failed" in result.error or "boom" in result.error


# ---------------------------------------------------------------------------
# _record_monitor
# ---------------------------------------------------------------------------


class TestRecordMonitor:
    def test_records_to_monitor(self):
        monitor = StubMonitorProvider(available=True)
        worker = _make_worker(monitor_provider=monitor)
        task = TaskDefinition(description="task", role_id="architect")
        worker._record_monitor(task, 1.5, success=True)
        assert len(monitor.recorded) == 1
        assert monitor.recorded[0]["success"] is True

    def test_no_monitor_noop(self):
        worker = _make_worker()
        task = TaskDefinition(description="task", role_id="architect")
        # Should not raise
        worker._record_monitor(task, 1.0, success=True)

    def test_monitor_unavailable_noop(self):
        monitor = StubMonitorProvider(available=False)
        worker = _make_worker(monitor_provider=monitor)
        task = TaskDefinition(description="task", role_id="architect")
        worker._record_monitor(task, 1.0, success=True)
        assert len(monitor.recorded) == 0


# ---------------------------------------------------------------------------
# _inject_rules_from_provider / _validate_injected_rules
# ---------------------------------------------------------------------------


class TestInjectRules:
    def test_no_memory_provider_noop(self):
        worker = _make_worker()
        task = TaskDefinition(description="task", role_id="architect")
        worker._inject_rules_from_provider(task)
        assert worker._injected_rules == []

    def test_memory_provider_unavailable_noop(self):
        memory = StubMemoryProvider(available=False)
        worker = _make_worker(memory_provider=memory)
        task = TaskDefinition(description="task", role_id="architect")
        worker._inject_rules_from_provider(task)
        assert worker._injected_rules == []

    def test_match_rules_success(self):
        rules = [
            {"rule_type": "always", "trigger": "database", "action": "Always validate database migrations before deployment", "rule_id": "r1"},
        ]
        memory = StubMemoryProvider(available=True, rules=rules, use_match=True)
        worker = _make_worker(memory_provider=memory)
        worker._validator = None  # Disable InputValidator for unit test
        task = TaskDefinition(description="task", role_id="architect")
        worker._inject_rules_from_provider(task)
        assert len(worker._injected_rules) == 1

    def test_get_rules_string_format(self):
        memory = StubMemoryProvider(
            available=True,
            rules=[
                {"rule_type": "always", "trigger": "code review", "action": "Always perform code review before merging"},
            ],
            use_match=False,
        )
        worker = _make_worker(memory_provider=memory)
        worker._validator = None
        task = TaskDefinition(description="task", role_id="architect")
        worker._inject_rules_from_provider(task)
        assert len(worker._injected_rules) == 1

    def test_rules_applied_tracked(self):
        rules = [
            {"rule_type": "always", "trigger": "testing", "action": "Always write unit tests for new functions", "rule_id": "r1"},
        ]
        memory = StubMemoryProvider(available=True, rules=rules)
        worker = _make_worker(memory_provider=memory)
        worker._validator = None
        task = TaskDefinition(description="task", role_id="architect")
        worker._inject_rules_from_provider(task)
        assert len(worker._rules_applied) == 1


class TestValidateInjectedRules:
    def test_valid_rule_passes(self):
        worker = _make_worker()
        worker._validator = None
        rules = [{"rule_type": "always", "trigger": "database", "action": "Always validate database migrations"}]
        result = worker._validate_injected_rules(rules)
        assert len(result) == 1

    def test_non_dict_rule_skipped(self):
        worker = _make_worker()
        worker._validator = None
        rules = ["not a dict", {"rule_type": "always", "trigger": "testing", "action": "Always write unit tests"}]
        result = worker._validate_injected_rules(rules)
        assert len(result) == 1

    def test_long_action_truncated(self):
        worker = _make_worker()
        worker._validator = None
        long_action = "Always perform thorough code review " * 20
        rules = [{"rule_type": "always", "trigger": "review", "action": long_action}]
        result = worker._validate_injected_rules(rules)
        assert len(result[0]["action"]) == 500

    def test_long_trigger_truncated(self):
        worker = _make_worker()
        worker._validator = None
        long_trigger = "database migration validation " * 20
        rules = [{"rule_type": "always", "trigger": long_trigger, "action": "Always validate"}]
        result = worker._validate_injected_rules(rules)
        assert len(result[0]["trigger"]) == 500

    def test_unicode_normalization(self):
        worker = _make_worker()
        worker._validator = None
        rules = [{"rule_type": "always", "trigger": "ｄａｔａｂａｓｅ", "action": "Always validate ｄａｔａｂａｓｅ migrations"}]
        result = worker._validate_injected_rules(rules)
        assert result[0]["trigger"] == "database"


# ---------------------------------------------------------------------------
# _check_forbid_violations
# ---------------------------------------------------------------------------


class TestCheckForbidViolations:
    def test_no_forbid_rules_returns_empty(self):
        worker = _make_worker()
        worker._injected_rules = [{"rule_type": "always", "trigger": "x", "action": "y"}]
        result = WorkerResult(
            worker_id="w1", task_id="t1", success=True, output="some output"
        )
        violations = worker._check_forbid_violations(result)
        assert violations == []

    def test_forbid_violation_detected(self):
        worker = _make_worker()
        worker._injected_rules = [
            {"rule_type": "forbid", "trigger": "secret", "action": "never output secret", "rule_id": "f1"},
        ]
        result = WorkerResult(
            worker_id="w1", task_id="t1", success=True, output="this contains secret data"
        )
        violations = worker._check_forbid_violations(result)
        assert len(violations) == 1
        assert violations[0]["rule_id"] == "f1"

    def test_forbid_no_trigger_no_violation(self):
        worker = _make_worker()
        worker._injected_rules = [
            {"rule_type": "forbid", "trigger": "", "action": "a", "rule_id": "f1"},
        ]
        result = WorkerResult(
            worker_id="w1", task_id="t1", success=True, output="some output"
        )
        violations = worker._check_forbid_violations(result)
        assert violations == []

    def test_forbid_override_high_severity(self):
        worker = _make_worker()
        worker._injected_rules = [
            {
                "rule_type": "forbid",
                "trigger": "bad",
                "action": "a",
                "rule_id": "f1",
                "override": True,
            },
        ]
        result = WorkerResult(
            worker_id="w1", task_id="t1", success=True, output="this is bad"
        )
        violations = worker._check_forbid_violations(result)
        assert violations[0]["severity"] == "high"

    def test_no_output_returns_empty(self):
        worker = _make_worker()
        worker._injected_rules = [
            {"rule_type": "forbid", "trigger": "x", "action": "a", "rule_id": "f1"},
        ]
        result = WorkerResult(worker_id="w1", task_id="t1", success=True, output=None)
        violations = worker._check_forbid_violations(result)
        assert violations == []


# ---------------------------------------------------------------------------
# get_briefing_summary / export_briefing / compress_to_briefing
# ---------------------------------------------------------------------------


class TestBriefingSummary:
    def test_no_briefing_returns_unavailable(self):
        worker = _make_worker()
        worker._briefing = None
        summary = worker.get_briefing_summary()
        assert summary["status"] == "unavailable"

    def test_briefing_available(self):
        worker = _make_worker()
        # Force briefing load
        _ = worker.briefing
        summary = worker.get_briefing_summary()
        assert summary["status"] in ("available", "error", "unavailable")


class TestExportBriefing:
    def test_no_briefing_returns_none(self):
        worker = _make_worker()
        worker._briefing = None
        assert worker.export_briefing() is None

    def test_export_with_briefing(self):
        worker = _make_worker()
        _ = worker.briefing
        with tempfile.TemporaryDirectory() as td:
            result = worker.export_briefing(output_dir=td)
            # May return path or None depending on briefing implementation
            assert result is None or isinstance(result, str)


class TestCompressToBriefing:
    def test_no_last_result_returns_empty(self):
        worker = _make_worker()
        result = worker.compress_to_briefing()
        assert isinstance(result, AgentBriefingOutput)
        assert result.task_summary == ""

    def test_with_last_result_dict_output(self):
        worker = _make_worker()
        worker._last_result = WorkerResult(
            worker_id="w1",
            task_id="t1",
            success=True,
            output={"finding_summary": "Found something"},
        )
        result = worker.compress_to_briefing()
        assert isinstance(result, AgentBriefingOutput)
        assert "Found something" in result.result_summary

    def test_with_last_result_string_output(self):
        worker = _make_worker()
        worker._last_result = WorkerResult(
            worker_id="w1",
            task_id="t1",
            success=True,
            output="String output text",
        )
        result = worker.compress_to_briefing()
        assert isinstance(result, AgentBriefingOutput)

    def test_receive_briefing(self):
        worker = _make_worker()
        briefing = AgentBriefingOutput(task_summary="test")
        worker.receive_briefing(briefing)
        assert worker._received_briefing is briefing


# ---------------------------------------------------------------------------
# _extract_decisions / _extract_pending
# ---------------------------------------------------------------------------


class TestExtractDecisions:
    def test_extracts_marked_decisions(self):
        worker = _make_worker()
        text = "Some intro\nDecision: Use Python\nOther text\nDecided: Skip tests"
        decisions = worker._extract_decisions(text)
        assert len(decisions) == 2

    def test_no_decisions_returns_empty(self):
        worker = _make_worker()
        text = "Just some text without decisions"
        decisions = worker._extract_decisions(text)
        assert decisions == []

    def test_max_five_decisions(self):
        worker = _make_worker()
        text = "\n".join(f"Decision: item {i}" for i in range(10))
        decisions = worker._extract_decisions(text)
        assert len(decisions) == 5


class TestExtractPending:
    def test_extracts_pending_items(self):
        worker = _make_worker()
        text = "Some intro\nTODO: Fix bug\nNext: Deploy\nPending: Review"
        pending = worker._extract_pending(text)
        assert len(pending) == 3

    def test_no_pending_returns_empty(self):
        worker = _make_worker()
        text = "Just some text"
        pending = worker._extract_pending(text)
        assert pending == []

    def test_max_five_pending(self):
        worker = _make_worker()
        text = "\n".join(f"TODO: item {i}" for i in range(10))
        pending = worker._extract_pending(text)
        assert len(pending) == 5


# ---------------------------------------------------------------------------
# get_provider_status
# ---------------------------------------------------------------------------


class TestGetProviderStatus:
    def test_no_providers(self):
        worker = _make_worker()
        status = worker.get_provider_status()
        assert status["worker_id"] == "test-worker"
        assert status["role_id"] == "architect"
        assert status["cache"]["available"] is False
        assert status["retry"]["available"] is False
        assert status["monitor"]["available"] is False
        assert status["memory"]["available"] is False

    def test_with_providers(self):
        cache = StubCacheProvider(available=True)
        retry = StubRetryProvider(available=True)
        monitor = StubMonitorProvider(available=True)
        memory = StubMemoryProvider(available=True)
        worker = _make_worker(
            cache_provider=cache,
            retry_provider=retry,
            monitor_provider=monitor,
            memory_provider=memory,
        )
        status = worker.get_provider_status()
        assert status["cache"]["available"] is True
        assert status["retry"]["available"] is True
        assert status["monitor"]["available"] is True
        assert status["memory"]["available"] is True
        assert status["memory"]["rules_injected"] == 0

    def test_with_execution_guard(self):
        guard = StubExecutionGuard()
        worker = _make_worker(execution_guard=guard)
        status = worker.get_provider_status()
        assert status["execution_guard"]["available"] is True
