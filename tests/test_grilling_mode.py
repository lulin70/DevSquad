#!/usr/bin/env python3
"""Module 10 (Matt P0-7): Grilling mode — one-question-at-a-time interview.

Tests for ``GrillingMode``, ``GrillingQuestion``, ``GrillingResult`` in
``rule_collector.py`` and ``inject_grilling_discipline()`` /
``PromptAssembler._inject_explore_before_ask()`` in ``prompt_assembler.py``,
added as part of V4.1.0 Matt Pocock skills fusion.

Acceptance criteria (PRD §3.1 P0-7): ≥12 tests covering grilling_mode +
explore-before-ask + integration with CodeKnowledgeGraph.
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.prompt_assembler import PromptAssembler, inject_grilling_discipline
from scripts.collaboration.rule_collector import (
    GrillingMode,
    GrillingQuestion,
    GrillingResult,
    RuleCollector,
)

# ======================================================================
# Module 10 — Matt Pocock Grilling Mode: Dataclasses
# ======================================================================


class TestGrillingQuestionDataclass(unittest.TestCase):
    """T1: GrillingQuestion dataclass defaults."""

    def test_default_values(self) -> None:
        """Verify: GrillingQuestion defaults to empty fields."""
        q = GrillingQuestion()
        self.assertEqual(q.question, "")
        self.assertEqual(q.recommended_answers, [])
        self.assertEqual(q.context, "")
        self.assertEqual(q.branch, "")
        self.assertFalse(q.explored)
        self.assertEqual(q.explored_answer, "")
        self.assertEqual(q.user_answer, "")


class TestGrillingResultDataclass(unittest.TestCase):
    """T2: GrillingResult dataclass defaults."""

    def test_default_values(self) -> None:
        """Verify: GrillingResult defaults to empty session."""
        r = GrillingResult()
        self.assertEqual(r.questions, [])
        self.assertFalse(r.completed)
        self.assertEqual(r.explored_answers, {})


# ======================================================================
# GrillingMode — add_question
# ======================================================================


class TestGrillingModeAddQuestion(unittest.TestCase):
    """T3-T4: Adding questions to the grilling queue."""

    def setUp(self) -> None:
        self.session = GrillingMode()

    def test_add_single_question(self) -> None:
        """Verify: add_question stores the question text."""
        self.session.add_question(question="Which framework?")
        q = self.session.current_question()
        assert q is not None
        self.assertEqual(q.question, "Which framework?")
        self.assertEqual(q.recommended_answers, [])

    def test_add_question_with_recommendations_and_context(self) -> None:
        """Verify: add_question stores recommendations, context, branch."""
        self.session.add_question(
            question="Which logging library?",
            recommended_answers=["structlog", "logging"],
            context="Need structured logging",
            branch="observability",
        )
        q = self.session.current_question()
        assert q is not None
        self.assertEqual(q.question, "Which logging library?")
        self.assertEqual(q.recommended_answers, ["structlog", "logging"])
        self.assertEqual(q.context, "Need structured logging")
        self.assertEqual(q.branch, "observability")


# ======================================================================
# GrillingMode — next_question / current_question
# ======================================================================


class TestGrillingModeNavigation(unittest.TestCase):
    """T5-T8: Question pointer navigation."""

    def setUp(self) -> None:
        self.session = GrillingMode()
        self.session.add_question("Q1?")
        self.session.add_question("Q2?")
        self.session.add_question("Q3?")

    def test_next_question_advances_pointer(self) -> None:
        """Verify: next_question returns questions in order and advances."""
        q1 = self.session.next_question()
        q2 = self.session.next_question()
        q3 = self.session.next_question()
        assert q1 is not None and q2 is not None and q3 is not None
        self.assertEqual(q1.question, "Q1?")
        self.assertEqual(q2.question, "Q2?")
        self.assertEqual(q3.question, "Q3?")

    def test_next_question_returns_none_when_exhausted(self) -> None:
        """Verify: next_question returns None after all questions consumed."""
        for _ in range(3):
            self.session.next_question()
        self.assertIsNone(self.session.next_question())

    def test_current_question_does_not_advance(self) -> None:
        """Verify: current_question returns same question on repeated calls."""
        q_first = self.session.current_question()
        q_second = self.session.current_question()
        assert q_first is not None and q_second is not None
        self.assertEqual(q_first.question, "Q1?")
        self.assertEqual(q_second.question, "Q1?")

    def test_current_question_returns_none_when_complete(self) -> None:
        """Verify: current_question returns None after pointer exhausted."""
        for _ in range(3):
            self.session.next_question()
        self.assertIsNone(self.session.current_question())


# ======================================================================
# GrillingMode — is_complete
# ======================================================================


class TestGrillingModeIsComplete(unittest.TestCase):
    """T9-T11: Completion checking."""

    def test_empty_session_is_complete(self) -> None:
        """Verify: a session with no questions is trivially complete."""
        session = GrillingMode()
        self.assertTrue(session.is_complete())

    def test_unanswered_questions_not_complete(self) -> None:
        """Verify: session with unanswered questions is not complete."""
        session = GrillingMode()
        session.add_question("Q1?")
        session.add_question("Q2?")
        self.assertFalse(session.is_complete())

    def test_all_answered_is_complete(self) -> None:
        """Verify: session with all user_answers set is complete."""
        session = GrillingMode()
        session.add_question("Q1?")
        session.add_question("Q2?")
        session._questions[0].user_answer = "A1"
        session._questions[1].user_answer = "A2"
        self.assertTrue(session.is_complete())

    def test_explored_answer_counts_as_answered(self) -> None:
        """Verify: explored_answer (from codebase) counts toward completion."""
        session = GrillingMode()
        session.add_question("Q1?")
        session._questions[0].explored_answer = "found in codebase"
        self.assertTrue(session.is_complete())


# ======================================================================
# GrillingMode — explore_before_ask
# ======================================================================


class TestGrillingModeExploreBeforeAsk(unittest.TestCase):
    """T12-T14: Codebase exploration before asking the user."""

    def test_explore_returns_none_without_code_graph(self) -> None:
        """Verify: explore_before_ask returns None when no code_graph provided."""
        session = GrillingMode()
        q = GrillingQuestion(question="Should I use 'structlog'?", recommended_answers=[])
        result = session.explore_before_ask(q)
        self.assertIsNone(result)
        self.assertTrue(q.explored)

    def test_explore_finds_symbol_with_code_graph(self) -> None:
        """Verify: explore_before_ask queries code_graph and returns finding."""
        mock_symbol = MagicMock()
        mock_symbol.name = "structlog"
        mock_query = MagicMock()
        mock_query.find_symbol.return_value = [mock_symbol]
        mock_graph = MagicMock()
        mock_graph.query.return_value = mock_query

        session = GrillingMode(code_graph=mock_graph)
        q = GrillingQuestion(question="Should I use 'structlog'?", recommended_answers=[])
        result = session.explore_before_ask(q)
        self.assertIsNotNone(result)
        self.assertIn("structlog", result)
        self.assertEqual(q.explored_answer, result)
        mock_query.find_symbol.assert_called_with("structlog")

    def test_explore_caches_result(self) -> None:
        """Verify: calling explore_before_ask twice does not re-query."""
        mock_query = MagicMock()
        mock_query.find_symbol.return_value = []
        mock_graph = MagicMock()
        mock_graph.query.return_value = mock_query

        session = GrillingMode(code_graph=mock_graph)
        q = GrillingQuestion(question="What about 'pytest'?", recommended_answers=[])
        first = session.explore_before_ask(q)
        second = session.explore_before_ask(q)
        self.assertIsNone(first)
        self.assertIsNone(second)
        # query() should only be called once (cached via explored flag)
        mock_graph.query.assert_called_once()


# ======================================================================
# GrillingMode — answer_current
# ======================================================================


class TestGrillingModeAnswerCurrent(unittest.TestCase):
    """T15-T16: Recording user answers."""

    def test_answer_current_records_and_advances(self) -> None:
        """Verify: answer_current stores the answer and moves pointer forward."""
        session = GrillingMode()
        session.add_question("Q1?")
        session.add_question("Q2?")
        ok = session.answer_current("A1")
        self.assertTrue(ok)
        self.assertEqual(session._questions[0].user_answer, "A1")
        q2 = session.current_question()
        assert q2 is not None
        self.assertEqual(q2.question, "Q2?")

    def test_answer_current_returns_false_when_no_current(self) -> None:
        """Verify: answer_current returns False when no question to answer."""
        session = GrillingMode()
        self.assertFalse(session.answer_current("A1"))


# ======================================================================
# GrillingMode — get_summary
# ======================================================================


class TestGrillingModeGetSummary(unittest.TestCase):
    """T17: Summary retrieval."""

    def test_get_summary_returns_complete_result(self) -> None:
        """Verify: get_summary returns all questions, completion flag, explored."""
        session = GrillingMode()
        session.add_question("Q1?", recommended_answers=["R1"])
        session.add_question("Q2?")
        session._questions[0].user_answer = "A1"
        session._questions[1].explored_answer = "found"

        result = session.get_summary()
        self.assertIsInstance(result, GrillingResult)
        self.assertEqual(len(result.questions), 2)
        self.assertTrue(result.completed)
        self.assertEqual(result.explored_answers, {"Q2?": "found"})


# ======================================================================
# GrillingMode — _extract_search_terms
# ======================================================================


class TestGrillingModeExtractSearchTerms(unittest.TestCase):
    """T18-T21: Search term extraction from question text."""

    def test_extracts_quoted_terms(self) -> None:
        """Verify: quoted terms like 'structlog' are extracted."""
        terms = GrillingMode._extract_search_terms('Should I use "structlog" or \'logging\'?')
        self.assertIn("structlog", terms)
        self.assertIn("logging", terms)

    def test_extracts_snake_case(self) -> None:
        """Verify: snake_case identifiers are extracted."""
        terms = GrillingMode._extract_search_terms("What about my_function and another_func?")
        self.assertIn("my_function", terms)
        self.assertIn("another_func", terms)

    def test_extracts_camel_case(self) -> None:
        """Verify: CamelCase identifiers are extracted."""
        terms = GrillingMode._extract_search_terms("Should we use CodeKnowledgeGraph or MyService?")
        self.assertIn("CodeKnowledgeGraph", terms)
        self.assertIn("MyService", terms)

    def test_deduplicates_preserving_order(self) -> None:
        """Verify: duplicate terms are removed, order preserved."""
        terms = GrillingMode._extract_search_terms('"pytest" and pytest and "pytest"')
        self.assertEqual(terms.count("pytest"), 1)


# ======================================================================
# RuleCollector.grilling_mode — integration
# ======================================================================


class TestRuleCollectorGrillingMode(unittest.TestCase):
    """T22-T23: RuleCollector factory method."""

    def test_grilling_mode_creates_session(self) -> None:
        """Verify: grilling_mode() returns a GrillingMode instance."""
        collector = RuleCollector()
        session = collector.grilling_mode()
        self.assertIsInstance(session, GrillingMode)

    def test_grilling_mode_passes_code_graph(self) -> None:
        """Verify: code_graph is passed through to the session."""
        mock_graph = MagicMock()
        collector = RuleCollector()
        session = collector.grilling_mode(code_graph=mock_graph)
        self.assertIsInstance(session, GrillingMode)
        self.assertIs(session._code_graph, mock_graph)


# ======================================================================
# inject_grilling_discipline — prompt injection
# ======================================================================


class TestInjectGrillingDiscipline(unittest.TestCase):
    """T24-T26: Grilling discipline injection text."""

    def test_default_includes_all_principles(self) -> None:
        """Verify: default call includes all 4 grilling principles."""
        text = inject_grilling_discipline()
        self.assertIn("Grilling Discipline", text)
        self.assertIn("1 question(s) per turn", text)
        self.assertIn("recommended answer", text)
        self.assertIn("design tree", text)
        self.assertIn("explore the codebase", text)

    def test_without_explore_before_ask(self) -> None:
        """Verify: include_explore_before_ask=False omits codebase search."""
        text = inject_grilling_discipline(include_explore_before_ask=False)
        self.assertIn("Grilling Discipline", text)
        self.assertNotIn("explore the codebase", text)

    def test_max_questions_zero_returns_empty(self) -> None:
        """Verify: max_questions_per_turn=0 returns empty string."""
        text = inject_grilling_discipline(max_questions_per_turn=0)
        self.assertEqual(text, "")

    def test_max_questions_custom_value(self) -> None:
        """Verify: custom max_questions_per_turn is reflected in text."""
        text = inject_grilling_discipline(max_questions_per_turn=3)
        self.assertIn("3 question(s) per turn", text)


# ======================================================================
# PromptAssembler._inject_explore_before_ask
# ======================================================================


class TestPromptAssemblerExploreBeforeAsk(unittest.TestCase):
    """T27: PromptAssembler explore-before-ask method."""

    def test_returns_discipline_text(self) -> None:
        """Verify: _inject_explore_before_ask returns non-empty discipline."""
        assembler = PromptAssembler(role_id="pm", base_prompt="You are a PM.")
        text = assembler._inject_explore_before_ask()
        self.assertIn("Explore-Before-Ask", text)
        self.assertIn("find_symbol", text)
        self.assertIn("find_callers", text)

    def test_grilling_injection_built_in_init(self) -> None:
        """Verify: _grilling_injection is populated during __init__."""
        assembler = PromptAssembler(role_id="pm", base_prompt="You are a PM.")
        self.assertTrue(assembler._grilling_injection)
        self.assertIn("Grilling Discipline", assembler._grilling_injection)


# ======================================================================
# Full session workflow — integration
# ======================================================================


class TestGrillingModeFullWorkflow(unittest.TestCase):
    """T28: End-to-end grilling session workflow."""

    def test_full_session_with_explore_and_user_answers(self) -> None:
        """Verify: complete workflow — add, explore, answer, summarize."""
        mock_symbol = MagicMock()
        mock_symbol.name = "structlog"
        mock_query = MagicMock()
        mock_query.find_symbol.return_value = [mock_symbol]
        mock_graph = MagicMock()
        mock_graph.query.return_value = mock_query

        collector = RuleCollector()
        session = collector.grilling_mode(code_graph=mock_graph)

        # Q1: codebase has the answer — explore_before_ask finds it
        session.add_question(
            question="Should I use 'structlog'?",
            recommended_answers=["structlog", "logging"],
            context="Need structured logging",
            branch="observability",
        )
        # Q2: codebase is silent — user must answer
        session.add_question(
            question="What log level for production?",
            recommended_answers=["INFO", "WARNING"],
            context="Production log verbosity",
            branch="observability",
        )

        # Explore Q1 — codebase finds structlog
        q1 = session.current_question()
        assert q1 is not None
        explored = session.explore_before_ask(q1)
        self.assertIsNotNone(explored)
        self.assertIn("structlog", explored)
        session.answer_current("accept structlog")  # user confirms

        # Q2 — codebase silent, user answers directly
        session.answer_current("INFO")

        result = session.get_summary()
        self.assertTrue(result.completed)
        self.assertEqual(len(result.questions), 2)
        self.assertEqual(result.questions[0].user_answer, "accept structlog")
        self.assertEqual(result.questions[1].user_answer, "INFO")
        self.assertIn("Should I use 'structlog'?", result.explored_answers)


if __name__ == "__main__":
    unittest.main()
