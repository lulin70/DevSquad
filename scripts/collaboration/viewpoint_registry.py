"""V4.4.0 P0-2 Viewpoint Registry — TOGAF Architecture Views & Viewpoints.

Binds each of the 7 DevSquad roles to a formal TOGAF viewpoint, enabling
``ConsensusEngine`` to arbitrate SPLIT outcomes by viewpoint orthogonality
and ``PromptAssembler`` to inject viewpoint specs into role prompts.

Anti-ghost: module-level ``_call_counter_er`` increments on every public
method call.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Anti-ghost: module-level call counter (AG-1/AG-2)
_call_counter_er: int = 0


@dataclass
class Viewpoint:
    """TOGAF Architecture Viewpoint bound to a DevSquad role.

    Attributes:
        name: Human-readable viewpoint name (e.g. "threat").
        concerns: What this viewpoint addresses.
        model_elements: Which model elements it operates on.
        stakeholders: Who cares about this viewpoint.
        role_id: Bound DevSquad role id.
    """

    name: str
    concerns: list[str] = field(default_factory=list)
    model_elements: list[str] = field(default_factory=list)
    stakeholders: list[str] = field(default_factory=list)
    role_id: str = ""


@dataclass
class ConsistencyViolation:
    """A contradiction between two viewpoints on a shared model element.

    Attributes:
        role_a: First conflicting role id.
        role_b: Second conflicting role id.
        shared_element: The model element they disagree on.
        contradiction: Description of the contradiction.
    """

    role_a: str
    role_b: str
    shared_element: str
    contradiction: str


def _build_default_viewpoints() -> dict[str, Viewpoint]:
    """Construct the 7 TOGAF viewpoints for DevSquad roles.

    Role ids follow the DevSquad Role System (SKILL.md):
    architect / product-manager / security / tester / solo-coder / devops / ui-designer
    """
    return {
        "architect": Viewpoint(
            name="functional + data",
            concerns=["structure", "data flow", "performance", "module", "interface"],
            model_elements=["components", "entities", "relationships"],
            stakeholders=["architect", "developers"],
            role_id="architect",
        ),
        "security": Viewpoint(
            name="threat",
            concerns=["attack surface", "trust boundaries", "encryption", "vulnerability"],
            model_elements=["assets", "threats", "controls"],
            stakeholders=["security team", "compliance"],
            role_id="security",
        ),
        "tester": Viewpoint(
            name="quality",
            concerns=["coverage", "failure modes", "test strategy", "defect"],
            model_elements=["test cases", "defects"],
            stakeholders=["QA", "developers"],
            role_id="tester",
        ),
        "solo-coder": Viewpoint(
            name="implementation",
            concerns=["APIs", "algorithms", "code quality", "refactor", "interface"],
            model_elements=["classes", "functions", "modules", "api_contract"],
            stakeholders=["developers"],
            role_id="solo-coder",
        ),
        "devops": Viewpoint(
            name="deployment",
            concerns=["runtime", "infra", "CI/CD", "monitoring", "Docker", "Kubernetes"],
            model_elements=["pipelines", "services", "environments"],
            stakeholders=["DevOps", "SRE"],
            role_id="devops",
        ),
        "product-manager": Viewpoint(
            name="requirements",
            concerns=["stakeholder needs", "PRD", "user story", "competitor", "acceptance"],
            model_elements=["user stories", "acceptance criteria"],
            stakeholders=["PM", "business"],
            role_id="product-manager",
        ),
        "ui-designer": Viewpoint(
            name="interaction",
            concerns=["UX", "accessibility", "frontend", "visual", "prototype"],
            model_elements=["screens", "flows", "components"],
            stakeholders=["UI", "end users"],
            role_id="ui-designer",
        ),
    }


# Alias map for short role ids (CLI short IDs per SKILL.md)
_ROLE_ALIASES: dict[str, str] = {
    "pm": "product-manager",
    "coder": "solo-coder",
    "ui": "ui-designer",
    "arch": "architect",
    "sec": "security",
    "test": "tester",
    "infra": "devops",
}


def _resolve_role(role_id: str) -> str:
    """Resolve short role aliases to canonical role ids."""
    if role_id in _DEFAULT_VIEWPOINTS:
        return role_id
    return _ROLE_ALIASES.get(role_id, role_id)


# Module-level static registry (built at import time)
_DEFAULT_VIEWPOINTS: dict[str, Viewpoint] = _build_default_viewpoints()


class ViewpointRegistry:
    """Registry of 7 TOGAF viewpoints bound to DevSquad roles.

    Anti-ghost: every public method increments ``_call_counter_er``.
    """

    def __init__(self) -> None:
        self._viewpoints: dict[str, Viewpoint] = dict(_DEFAULT_VIEWPOINTS)

    def get(self, role_id: str) -> Viewpoint:
        """Return the viewpoint bound to a role.

        Args:
            role_id: Canonical role id or short alias.

        Returns:
            The Viewpoint for that role.

        Raises:
            KeyError: If role_id is not a known role.
        """
        global _call_counter_er
        _call_counter_er += 1

        canonical = _resolve_role(role_id)
        if canonical not in self._viewpoints:
            raise KeyError(
                f"Unknown role_id: {role_id!r}. "
                f"Known roles: {list(self._viewpoints.keys())}"
            )
        return self._viewpoints[canonical]

    def all(self) -> list[Viewpoint]:
        """Return all 7 viewpoints.

        Returns:
            List of all viewpoints, one per role.
        """
        global _call_counter_er
        _call_counter_er += 1
        return list(self._viewpoints.values())

    def is_orthogonal(self, role_a: str, role_b: str) -> bool:
        """Check if two roles' viewpoints are orthogonal (no shared concerns).

        Two viewpoints are orthogonal if they share no concerns. A role
        compared with itself is never orthogonal.

        Args:
            role_a: First role id.
            role_b: Second role id.

        Returns:
            True if the viewpoints share no concerns.
        """
        global _call_counter_er
        _call_counter_er += 1

        ca = _resolve_role(role_a)
        cb = _resolve_role(role_b)
        if ca == cb:
            return False
        vp_a = self._viewpoints.get(ca)
        vp_b = self._viewpoints.get(cb)
        if vp_a is None or vp_b is None:
            return False
        return len(set(vp_a.concerns) & set(vp_b.concerns)) == 0

    def check_consistency(
        self,
        outputs: dict[str, str] | None = None,
        *,
        viewpoint_a: str | None = None,
        viewpoint_b: str | None = None,
        shared_element: str | None = None,
        stance_a: str | None = None,
        stance_b: str | None = None,
    ) -> list[ConsistencyViolation]:
        """Flag contradictions on shared model elements across roles.

        Two modes:
        1. Full mode (``outputs`` dict): compare outputs of all non-orthogonal
           role pairs for shared model elements.
        2. Explicit mode (``viewpoint_a`` + ``viewpoint_b`` + ``shared_element``
           + ``stance_a`` + ``stance_b``): check a specific pair.

        Args:
            outputs: Mapping of role_id → output text (full mode).
            viewpoint_a: First role id (explicit mode).
            viewpoint_b: Second role id (explicit mode).
            shared_element: The model element they disagree on.
            stance_a: First role's stance on the element.
            stance_b: Second role's stance on the element.

        Returns:
            List of ConsistencyViolation objects.
        """
        global _call_counter_er
        _call_counter_er += 1

        # Explicit mode: caller specifies the pair and stances
        if viewpoint_a is not None and viewpoint_b is not None:
            return self._check_explicit_consistency(
                viewpoint_a, viewpoint_b, shared_element, stance_a, stance_b
            )

        # Full mode: compare all non-orthogonal pairs
        if outputs is None:
            return []
        return self._check_full_consistency(outputs)

    def _check_explicit_consistency(
        self,
        viewpoint_a: str,
        viewpoint_b: str,
        shared_element: str | None,
        stance_a: str | None,
        stance_b: str | None,
    ) -> list[ConsistencyViolation]:
        """Check a specific role pair for consistency violations."""
        ca = _resolve_role(viewpoint_a)
        cb = _resolve_role(viewpoint_b)
        vp_a = self._viewpoints.get(ca)
        vp_b = self._viewpoints.get(cb)
        if vp_a is None or vp_b is None:
            return []

        shared_elements_a = set(vp_a.model_elements)
        shared_elements_b = set(vp_b.model_elements)
        element = shared_element or ""

        # If stances disagree and the viewpoints share any model element,
        # flag a consistency violation.
        stances_disagree = (
            stance_a is not None
            and stance_b is not None
            and stance_a != stance_b
        )
        if not stances_disagree:
            return []

        shares_element = (
            element in shared_elements_a
            or element in shared_elements_b
            or len(shared_elements_a & shared_elements_b) > 0
        )
        if not shares_element:
            return []

        return [
            ConsistencyViolation(
                role_a=ca,
                role_b=cb,
                shared_element=element,
                contradiction=f"{stance_a} vs {stance_b}",
            )
        ]

    def _check_full_consistency(
        self,
        outputs: dict[str, str],
    ) -> list[ConsistencyViolation]:
        """Compare all non-orthogonal role pairs for contradictions."""
        violations: list[ConsistencyViolation] = []
        role_ids = list(outputs.keys())
        for i, ra in enumerate(role_ids):
            for rb in role_ids[i + 1 :]:
                if self.is_orthogonal(ra, rb):
                    continue  # Orthogonal — no conflict possible
                ca = _resolve_role(ra)
                cb = _resolve_role(rb)
                vp_a = self._viewpoints.get(ca)
                vp_b = self._viewpoints.get(cb)
                if vp_a is None or vp_b is None:
                    continue
                shared = set(vp_a.model_elements) & set(vp_b.model_elements)
                for elem in shared:
                    text_a = outputs[ra].lower()
                    text_b = outputs[rb].lower()
                    # Simple contradiction heuristic: one says "yes" other says "no"
                    if ("yes" in text_a and "no" in text_b) or (
                        "no" in text_a and "yes" in text_b
                    ):
                        violations.append(
                            ConsistencyViolation(
                                role_a=ca,
                                role_b=cb,
                                shared_element=elem,
                                contradiction=f"{ra} and {rb} disagree on {elem}",
                            )
                        )
        return violations
