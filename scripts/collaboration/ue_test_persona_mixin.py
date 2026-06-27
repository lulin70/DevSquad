"""User persona mixin for UETestFramework.

Extracts user-persona definition and persona-driven test scenario
generation so the main framework file can focus on orchestration.

Responsibilities (from IMPROVEMENT_PLAN_V3.9.2.md P2-3):
    - User persona definition & storage
    - Persona-based test scenario generation
    - Persona test-focus derivation
"""

from typing import Any

from .ue_test_framework_base import UETestFrameworkBase, UserPersona


class UETestPersonaMixin(UETestFrameworkBase):
    """Provides user persona definition and scenario generation."""

    def define_persona(
        self,
        name: str,
        tech_level: str,
        goals: list[str],
        frustrations: list[str],
    ) -> UserPersona:
        """Define a user persona for UE testing.

        Args:
            name: Persona name (e.g., "first-time-user", "power-user")
            tech_level: "beginner" | "intermediate" | "advanced"
            goals: What this persona wants to achieve
            frustrations: Common pain points for this persona

        Returns:
            Created UserPersona instance.
        """
        persona = UserPersona(
            name=name,
            tech_level=tech_level,
            goals=goals,
            frustrations=frustrations,
        )
        self._personas.append(persona)
        return persona

    def _generate_persona_scenarios(self) -> list[dict[str, Any]]:
        """Generate test scenarios from defined personas."""
        scenarios = []
        for persona in self._personas:
            scenarios.append(
                {
                    "persona": persona.name,
                    "tech_level": persona.tech_level,
                    "goals": persona.goals,
                    "frustrations": persona.frustrations,
                    "patience_threshold": persona.patience_threshold,
                    "test_focus": self._persona_test_focus(persona),
                }
            )
        if not scenarios:
            scenarios.append(
                {
                    "persona": "default-user",
                    "tech_level": "intermediate",
                    "goals": ["Complete core task"],
                    "frustrations": ["Confusing navigation"],
                    "patience_threshold": 0.7,
                    "test_focus": ["core_journey", "error_recovery"],
                }
            )
        return scenarios

    def _persona_test_focus(self, persona: UserPersona) -> list[str]:
        """Determine test focus areas based on persona characteristics."""
        focus = []
        if persona.tech_level == "beginner":
            focus.extend(["onboarding", "discoverability", "error_prevention"])
        elif persona.tech_level == "advanced":
            focus.extend(["shortcuts", "customization", "efficiency"])
        else:
            focus.extend(["core_journey", "error_recovery"])

        if persona.patience_threshold < 0.5:
            focus.append("response_time")
        if len(persona.frustrations) > 2:
            focus.append("frustration_handling")

        return focus
