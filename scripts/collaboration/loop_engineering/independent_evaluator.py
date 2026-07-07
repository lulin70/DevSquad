"""Verification 阶段：独立评估 Generator 产出。"""

from __future__ import annotations

from typing import Any

from .models import EvaluatorMode


class IndependentEvaluator:
    """独立评估产出质量。

    STRICT: 必须通过才算成功。
    STANDARD: 允许自评 + 抽检。
    OFF: 关闭。
    """

    def __init__(
        self,
        mode: EvaluatorMode = EvaluatorMode.STRICT,
        validator: Any = None,
    ) -> None:
        self._mode = mode
        self._validator = validator

    def evaluate(
        self,
        objective: str,
        handoff_result: dict[str, Any],
        _iter_index: int,
    ) -> tuple[bool, list[str]]:
        if self._mode == EvaluatorMode.OFF:
            return True, []

        errors: list[str] = []

        if handoff_result.get("status") == "error":
            errors.append(f"Handoff error: {handoff_result.get('error', 'unknown')}")

        if handoff_result.get("status") == "skipped" and handoff_result.get("tasks") == []:
            return True, []

        output = handoff_result.get("output", "")
        if not output and self._mode == EvaluatorMode.STRICT:
            errors.append("Empty output in STRICT mode")

        if self._validator is not None:
            try:
                validator_errors = self._validator(objective, handoff_result)
                errors.extend(validator_errors)
            except Exception as exc:
                errors.append(f"Validator exception: {exc}")

        if self._mode == EvaluatorMode.STANDARD and len(errors) <= 1:
            return True, errors

        return len(errors) == 0, errors
