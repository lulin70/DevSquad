"""V4.4.0 P0-1 Risk Register — PMP Risk Management for DevSquad 11-phase lifecycle.

Records risks with probability × impact assessment, supports 7-role voting,
applies one of 4 PMP response strategies (avoid/transfer/mitigate/accept),
and exports a Markdown "Risk Management" section for the dispatch report.

Anti-ghost: module-level ``_call_counter`` increments on every public method
call, verifiable by E2E test E13 (``test_e2e_dispatch_increments_all_five_counters``).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any

# Anti-ghost: module-level call counter (AG-1/AG-2)
_call_counter: int = 0


class ResponseStrategy(Enum):
    """PMP 4 risk response strategies."""

    AVOID = "avoid"
    TRANSFER = "transfer"
    MITIGATE = "mitigate"
    ACCEPT = "accept"


class RiskStatus(Enum):
    """Lifecycle status of a risk item."""

    OPEN = "open"
    MITIGATING = "mitigating"
    CLOSED = "closed"


def _coerce_strategy(value: Any) -> ResponseStrategy:
    """Accept str or ResponseStrategy; raise ValueError on unknown."""
    if isinstance(value, ResponseStrategy):
        return value
    if isinstance(value, str):
        try:
            return ResponseStrategy(value.lower())
        except ValueError as exc:
            raise ValueError(
                f"Unknown response_strategy: {value!r}. "
                f"Must be one of {[s.value for s in ResponseStrategy]}"
            ) from exc
    raise TypeError(f"response_strategy must be str or ResponseStrategy, got {type(value)!r}")


def _coerce_status(value: Any) -> RiskStatus:
    """Accept str or RiskStatus; raise ValueError on unknown."""
    if isinstance(value, RiskStatus):
        return value
    if isinstance(value, str):
        try:
            return RiskStatus(value.lower())
        except ValueError as exc:
            raise ValueError(
                f"Unknown status: {value!r}. "
                f"Must be one of {[s.value for s in RiskStatus]}"
            ) from exc
    raise TypeError(f"status must be str or RiskStatus, got {type(value)!r}")


@dataclass
class RiskItem:
    """A single risk entry in the register.

    Attributes:
        id: Stable unique identifier (deterministic hash of description).
        description: Human-readable risk description.
        probability: Likelihood 0.0-1.0.
        impact: Severity 0.0-1.0.
        response_strategy: One of 4 PMP strategies.
        owner: Role id responsible for the risk.
        status: Lifecycle status (OPEN/MITIGATING/CLOSED).
        category: Risk category (e.g. "technical", "security", "schedule").
    """

    id: str
    description: str
    probability: float
    impact: float
    response_strategy: ResponseStrategy = ResponseStrategy.ACCEPT
    owner: str = ""
    status: RiskStatus = RiskStatus.OPEN
    category: str = "general"

    def __post_init__(self) -> None:
        """Coerce str fields to enums for E2E convenience."""
        self.response_strategy = _coerce_strategy(self.response_strategy)
        self.status = _coerce_status(self.status)

    @property
    def exposure(self) -> float:
        """Risk exposure score = probability × impact."""
        return self.probability * self.impact


# 7-role weights for weighted-mean voting (PRD AC-R2)
ROLE_WEIGHTS: dict[str, float] = {
    "architect": 3.0,
    "security": 2.5,
    "product-manager": 2.0,
    "pm": 2.0,
    "tester": 1.5,
    "solo-coder": 1.5,
    "coder": 1.5,
    "devops": 1.0,
    "ui-designer": 1.0,
    "ui": 1.0,
}

# Exposure threshold for RISK_CHECK gate (PRD AC-R5)
EXPOSURE_THRESHOLD: float = 0.36


class RiskRegister:
    """Persistent risk register with 7-role voting and Markdown export.

    Anti-ghost: every public method increments the module-level
    ``_call_counter``. The read-only ``_call_counter`` property exposes
    it on instances for E2E test verification (``register._call_counter``).
    """

    def __init__(self) -> None:
        self._items: dict[str, RiskItem] = {}

    @property
    def _call_counter(self) -> int:
        """Expose module-level call counter on instances (anti-ghost)."""
        return _call_counter

    def add(
        self,
        risk_item: RiskItem | None = None,
        *,
        description: str | None = None,
        probability: float = 0.0,
        impact: float = 0.0,
        category: str = "general",
        owner: str = "",
    ) -> RiskItem:
        """Add a risk to the register.

        Accepts either a pre-constructed ``RiskItem`` (E2E contract) or
        keyword arguments (PRD §3.1.3 signature). If ``risk_item`` is
        provided, its ``id`` is preserved; otherwise a deterministic id
        is generated from the description.

        Returns:
            The stored RiskItem.
        """
        global _call_counter
        _call_counter += 1

        if risk_item is not None:
            item = risk_item
            if not item.id:
                item.id = self._generate_id(item.description)
        else:
            if description is None:
                raise ValueError("Either risk_item or description must be provided")
            rid = self._generate_id(description)
            item = RiskItem(
                id=rid,
                description=description,
                probability=probability,
                impact=impact,
                category=category,
                owner=owner,
            )
        self._items[item.id] = item
        return item

    def assess(
        self,
        risk_id: str,
        votes: dict[str, tuple[float, float]] | None = None,
    ) -> RiskItem:
        """Apply 7-role weighted voting to update probability/impact.

        Args:
            risk_id: The risk to assess.
            votes: Mapping of role_id → (probability, impact).

        Returns:
            Updated RiskItem.

        Raises:
            KeyError: If risk_id not in register.
            ValueError: If a role_id is not in ROLE_WEIGHTS.
        """
        global _call_counter
        _call_counter += 1

        if risk_id not in self._items:
            raise KeyError(f"Unknown risk_id: {risk_id!r}")

        if not votes:
            return self._items[risk_id]

        total_weight = 0.0
        sum_p = 0.0
        sum_i = 0.0
        for role_id, (p, i) in votes.items():
            weight = ROLE_WEIGHTS.get(role_id)
            if weight is None:
                raise ValueError(
                    f"Unknown role_id: {role_id!r}. "
                    f"Must be one of {list(ROLE_WEIGHTS.keys())}"
                )
            total_weight += weight
            sum_p += weight * p
            sum_i += weight * i

        if total_weight > 0:
            item = self._items[risk_id]
            item.probability = sum_p / total_weight
            item.impact = sum_i / total_weight
        return self._items[risk_id]

    def mitigate(
        self,
        risk_id: str,
        strategy: ResponseStrategy | str,
        owner: str,
        plan: str = "",
    ) -> RiskItem:
        """Record a mitigation strategy and set status to MITIGATING.

        Args:
            risk_id: The risk to mitigate.
            strategy: One of 4 PMP ResponseStrategy values (str or enum).
            owner: Role id taking ownership.
            plan: Optional mitigation plan text.

        Returns:
            Updated RiskItem.
        """
        global _call_counter
        _call_counter += 1

        if risk_id not in self._items:
            raise KeyError(f"Unknown risk_id: {risk_id!r}")

        item = self._items[risk_id]
        item.response_strategy = _coerce_strategy(strategy)
        item.owner = owner
        item.status = RiskStatus.MITIGATING
        if plan:
            item.description = f"{item.description}\n[Mitigation Plan] {plan}"
        return item

    def track(
        self,
        risk_id: str,
        status: RiskStatus | str,
    ) -> RiskItem:
        """Update the lifecycle status of a risk.

        Args:
            risk_id: The risk to track.
            status: New status (str or RiskStatus).

        Returns:
            Updated RiskItem.
        """
        global _call_counter
        _call_counter += 1

        if risk_id not in self._items:
            raise KeyError(f"Unknown risk_id: {risk_id!r}")

        item = self._items[risk_id]
        item.status = _coerce_status(status)
        return item

    def query(
        self,
        status: RiskStatus | str | None = None,
        category: str | None = None,
    ) -> list[RiskItem]:
        """Query risks by optional status and/or category filters.

        Args:
            status: If provided, filter by this status.
            category: If provided, filter by this category.

        Returns:
            List of matching RiskItem objects.
        """
        global _call_counter
        _call_counter += 1

        target_status = _coerce_status(status) if status is not None else None
        results: list[RiskItem] = []
        for item in self._items.values():
            if target_status is not None and item.status != target_status:
                continue
            if category is not None and item.category != category:
                continue
            results.append(item)
        return results

    def export_markdown(self) -> str:
        """Render the 'Risk Management' section, sorted by exposure descending.

        Returns:
            Markdown string with ``## Risk Management`` header and a table
            of open risks.
        """
        global _call_counter
        _call_counter += 1

        open_risks = [r for r in self._items.values() if r.status == RiskStatus.OPEN]
        open_risks.sort(key=lambda r: r.exposure, reverse=True)

        if not open_risks:
            return "## Risk Management\n\n_No open risks._\n"

        lines = [
            "## Risk Management",
            "",
            "| ID | Description | Probability | Impact | Exposure | Strategy | Owner | Category |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for r in open_risks:
            lines.append(
                f"| {r.id} | {r.description[:60]} | {r.probability:.2f} | "
                f"{r.impact:.2f} | {r.exposure:.4f} | "
                f"{r.response_strategy.value} | {r.owner} | {r.category} |"
            )
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _generate_id(description: str) -> str:
        """Generate a deterministic id from the description via SHA256[:12]."""
        return "R-" + hashlib.sha256(description.encode("utf-8")).hexdigest()[:12]
