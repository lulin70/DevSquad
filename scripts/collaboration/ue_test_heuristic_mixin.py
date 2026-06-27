"""Usability heuristic mixin for UETestFramework.

Extracts Nielsen's 10 usability heuristic assessment (rule-based and
LLM-assisted) and the associated keyword/recommendation tables so the
main framework file can focus on orchestration.

Responsibilities (from IMPROVEMENT_PLAN_V3.9.2.md P2-3):
    - Nielsen's 10 heuristic assessment
    - Rule-based keyword matching
    - LLM-assisted assessment (with rule-based fallback)
    - Heuristic keyword & recommendation tables
"""

import logging

from .ue_test_framework_base import HeuristicCheck, UETestFrameworkBase, UsabilityReport

logger = logging.getLogger(__name__)


class UETestHeuristicMixin(UETestFrameworkBase):
    """Provides Nielsen's 10 heuristic usability assessment."""

    def assess_usability(self, interface_description: str) -> UsabilityReport:
        """Assess usability against Nielsen's 10 heuristics.

        Uses LLM if available, otherwise rule-based assessment.

        Args:
            interface_description: Description of the interface to assess.

        Returns:
            UsabilityReport with heuristic evaluation results.
        """
        if self.llm_backend is not None:
            return self._assess_with_llm(interface_description)
        return self._assess_rule_based(interface_description)

    def _assess_rule_based(self, interface_description: str) -> UsabilityReport:
        """Rule-based heuristic assessment using keyword matching."""
        lower_desc = interface_description.lower()
        assessed = []
        critical_issues = []
        recommendations = []

        for h in self._heuristics:
            check = HeuristicCheck(
                name=h.name,
                description=h.description,
            )
            positive_keywords = self._heuristic_positive_keywords(h.name)
            negative_keywords = self._heuristic_negative_keywords(h.name)

            pos_score = sum(1 for kw in positive_keywords if kw in lower_desc)
            neg_score = sum(1 for kw in negative_keywords if kw in lower_desc)

            if neg_score > 0:
                check.passed = False
                check.severity = "major" if neg_score > 1 else "minor"
                check.evidence = f"Found {neg_score} violation indicator(s)"
                critical_issues.append(f"{h.name}: {check.evidence}")
                recommendations.append(self._heuristic_recommendation(h.name))
            elif pos_score > 0:
                check.passed = True
                check.evidence = f"Found {pos_score} positive indicator(s)"
            else:
                check.passed = None
                check.evidence = "No indicators found in description"

            assessed.append(check)

        passed_count = sum(1 for h in assessed if h.passed is True)
        total = len(assessed)
        overall = passed_count / max(total, 1)

        return UsabilityReport(
            heuristics=assessed,
            overall_score=overall,
            critical_issues=critical_issues,
            recommendations=recommendations,
        )

    def _assess_with_llm(self, interface_description: str) -> UsabilityReport:
        """LLM-assisted heuristic assessment."""
        try:
            prompt = self._build_usability_prompt(interface_description)
            response = self.llm_backend.generate(prompt)
            return self._parse_llm_usability_response(response)
        except (RuntimeError, ValueError, TypeError, ConnectionError) as e:
            logger.debug("LLM usability assessment failed, falling back to rule-based: %s", e)
            return self._assess_rule_based(interface_description)

    def _build_usability_prompt(self, description: str) -> str:
        heuristic_list = "\n".join(
            f"{i+1}. {h.name}: {h.description}" for i, h in enumerate(self._heuristics)
        )
        return (
            f"Assess the following interface against Nielsen's 10 usability heuristics.\n"
            f"Interface description:\n{description}\n\n"
            f"Heuristics:\n{heuristic_list}\n\n"
            f"For each heuristic, provide:\n"
            f"- passed: true/false\n"
            f"- evidence: brief explanation\n"
            f"- severity: cosmetic/minor/major/critical (if failed)\n\n"
            f"Respond in JSON format with 'heuristics' array and 'recommendations' array."
        )

    def _parse_llm_usability_response(self, response: str) -> UsabilityReport:
        """Parse LLM response into UsabilityReport."""
        import json

        try:
            data = json.loads(response)
        except (json.JSONDecodeError, TypeError):
            return self._assess_rule_based(response)

        heuristics = []
        critical_issues = []
        for item in data.get("heuristics", []):
            h = HeuristicCheck(
                name=item.get("name", ""),
                description=item.get("description", ""),
                passed=item.get("passed"),
                evidence=item.get("evidence", ""),
                severity=item.get("severity", ""),
            )
            heuristics.append(h)
            if h.passed is False and h.severity in ("major", "critical"):
                critical_issues.append(f"{h.name}: {h.evidence}")

        recommendations = data.get("recommendations", [])
        passed_count = sum(1 for h in heuristics if h.passed is True)
        overall = passed_count / max(len(heuristics), 1)

        return UsabilityReport(
            heuristics=heuristics,
            overall_score=overall,
            critical_issues=critical_issues,
            recommendations=recommendations,
        )

    def _default_heuristics(self) -> list[HeuristicCheck]:
        """Nielsen's 10 usability heuristics as checkable items."""
        return [
            HeuristicCheck(
                "visibility_of_system_status",
                "System should always keep users informed about what is going on",
            ),
            HeuristicCheck(
                "match_between_system_and_real_world",
                "System should speak the users' language",
            ),
            HeuristicCheck(
                "user_control_and_freedom",
                "Users need emergency exits from unwanted states",
            ),
            HeuristicCheck(
                "consistency_and_standards",
                "Users should not have to wonder whether different words mean the same thing",
            ),
            HeuristicCheck(
                "error_prevention",
                "Better than good error messages is careful design to prevent problems",
            ),
            HeuristicCheck(
                "recognition_rather_than_recall",
                "Minimize user memory load by making objects/actions visible",
            ),
            HeuristicCheck(
                "flexibility_and_efficiency_of_use",
                "Accelerators for expert users without hindering novices",
            ),
            HeuristicCheck(
                "aesthetic_and_minimalist_design",
                "Dialogues should not contain irrelevant information",
            ),
            HeuristicCheck(
                "help_users_recognize_diagnose_and_recover_from_errors",
                "Error messages should be expressed in plain language",
            ),
            HeuristicCheck(
                "help_and_documentation",
                "Users may need help, should be easy to search and focused on task",
            ),
        ]

    @staticmethod
    def _heuristic_positive_keywords(name: str) -> list[str]:
        """Keywords suggesting a heuristic is satisfied."""
        keyword_map = {
            "visibility_of_system_status": ["loading", "progress", "status", "feedback", "indicator", "spinner"],
            "match_between_system_and_real_world": ["intuitive", "natural", "familiar", "real-world", "metaphor"],
            "user_control_and_freedom": ["undo", "cancel", "back", "redo", "rollback", "revert"],
            "consistency_and_standards": ["consistent", "standard", "uniform", "convention", "pattern"],
            "error_prevention": ["validation", "confirm", "preview", "warning", "guard", "constraint"],
            "recognition_rather_than_recall": ["visible", "icon", "menu", "dropdown", "suggestion", "autocomplete"],
            "flexibility_and_efficiency_of_use": ["shortcut", "keyboard", "macro", "template", "accelerator"],
            "aesthetic_and_minimalist_design": ["clean", "minimal", "simple", "focused", "uncluttered"],
            "help_users_recognize_diagnose_and_recover_from_errors": ["error message", "helpful", "suggestion", "recovery"],
            "help_and_documentation": ["help", "documentation", "tooltip", "guide", "tutorial", "search"],
        }
        return keyword_map.get(name, [])

    @staticmethod
    def _heuristic_negative_keywords(name: str) -> list[str]:
        """Keywords suggesting a heuristic is violated."""
        keyword_map = {
            "visibility_of_system_status": ["no feedback", "frozen", "unresponsive", "silent", "stuck"],
            "match_between_system_and_real_world": ["jargon", "technical term", "confusing label", "ambiguous"],
            "user_control_and_freedom": ["no undo", "no cancel", "irreversible", "trapped", "forced"],
            "consistency_and_standards": ["inconsistent", "different meaning", "confusing", "contradictory"],
            "error_prevention": ["easy to mistake", "no validation", "no confirmation", "destructive"],
            "recognition_rather_than_recall": ["remember", "hidden", "memorize", "invisible", "not visible"],
            "flexibility_and_efficiency_of_use": ["no shortcut", "slow", "tedious", "repetitive", "manual"],
            "aesthetic_and_minimalist_design": ["cluttered", "overwhelming", "busy", "too much", "crowded"],
            "help_users_recognize_diagnose_and_recover_from_errors": ["cryptic error", "error code", "unhelpful", "generic error"],
            "help_and_documentation": ["no help", "no documentation", "no tooltip", "no guide"],
        }
        return keyword_map.get(name, [])

    @staticmethod
    def _heuristic_recommendation(name: str) -> str:
        """Recommendation for a violated heuristic."""
        rec_map = {
            "visibility_of_system_status": "Add loading indicators, progress bars, or status messages for all async operations",
            "match_between_system_and_real_world": "Replace technical jargon with user-friendly language and familiar concepts",
            "user_control_and_freedom": "Add undo/cancel/revert options for all destructive or significant actions",
            "consistency_and_standards": "Standardize terminology, layout patterns, and interaction behaviors across the interface",
            "error_prevention": "Add input validation, confirmation dialogs, and constraints to prevent common mistakes",
            "recognition_rather_than_recall": "Make options visible with menus, icons, and suggestions instead of requiring memory",
            "flexibility_and_efficiency_of_use": "Add keyboard shortcuts, templates, and accelerators for expert users",
            "aesthetic_and_minimalist_design": "Remove irrelevant information and simplify the interface to focus on core tasks",
            "help_users_recognize_diagnose_and_recover_from_errors": "Write error messages in plain language with specific recovery suggestions",
            "help_and_documentation": "Add searchable help documentation, tooltips, and contextual guidance",
        }
        return rec_map.get(name, "Review and improve this aspect of the interface")
