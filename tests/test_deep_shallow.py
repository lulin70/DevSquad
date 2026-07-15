#!/usr/bin/env python3
"""Module 8 (Matt P0-5): Deep/shallow vocabulary — premature seam detection.

Tests for ``YagniChecker.check_premature_seam()``, ``PrematureSeamResult``
dataclass, and helper methods ``_get_base_name()`` / ``_is_abstract_class()``
added as part of V4.1.0 Matt Pocock skills fusion.

Acceptance criteria (PRD §3.1 P0-5): premature seam detection + >=10 tests.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.yagni_checker import PrematureSeamResult, YagniChecker

# ======================================================================
# Module 8 — Matt Pocock Deep/Shallow: PrematureSeamResult dataclass
# ======================================================================


class TestPrematureSeamResultDataclass(unittest.TestCase):
    """T1: PrematureSeamResult dataclass defaults."""

    def test_default_values(self) -> None:
        """Verify: PrematureSeamResult defaults to empty/zero fields."""
        r = PrematureSeamResult()
        self.assertEqual(r.seam_name, "")
        self.assertEqual(r.adapter_count, 0)
        self.assertFalse(r.is_premature)
        self.assertEqual(r.adapters, [])
        self.assertEqual(r.reason, "")


# ======================================================================
# check_premature_seam — no abstract classes
# ======================================================================


class TestCheckPrematureSeamNoAbstract(unittest.TestCase):
    """T2: Code with no abstract classes returns empty list."""

    def test_plain_code_returns_empty(self) -> None:
        """Verify: code with no ABC/Protocol returns empty list."""
        checker = YagniChecker()
        code = "class Foo:\n    pass\n\nclass Bar(Foo):\n    pass\n"
        results = checker.check_premature_seam(code)
        self.assertEqual(results, [])

    def test_plain_functions_only_returns_empty(self) -> None:
        """Verify: code with only functions (no classes) returns empty."""
        checker = YagniChecker()
        code = "def foo():\n    pass\n\ndef bar():\n    pass\n"
        results = checker.check_premature_seam(code)
        self.assertEqual(results, [])


# ======================================================================
# check_premature_seam — premature seam (1 adapter)
# ======================================================================


class TestCheckPrematureSeamPremature(unittest.TestCase):
    """T3-T4: Premature seam detection (only 1 implementation)."""

    def test_abc_with_one_impl_is_premature(self) -> None:
        """Verify: ABC with only 1 concrete implementation is premature."""
        checker = YagniChecker()
        code = (
            "from abc import ABC\n"
            "class DataStore(ABC):\n"
            "    pass\n"
            "\n"
            "class SqlStore(DataStore):\n"
            "    pass\n"
        )
        results = checker.check_premature_seam(code)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].seam_name, "DataStore")
        self.assertEqual(results[0].adapter_count, 1)
        self.assertTrue(results[0].is_premature)
        self.assertEqual(results[0].adapters, ["SqlStore"])
        self.assertIn("Premature seam", results[0].reason)

    def test_protocol_with_one_impl_is_premature(self) -> None:
        """Verify: Protocol with only 1 implementation is premature."""
        checker = YagniChecker()
        code = (
            "from typing import Protocol\n"
            "class Cache(Protocol):\n"
            "    def get(self, key: str) -> str: ...\n"
            "\n"
            "class RedisCache:\n"
            "    def get(self, key: str) -> str:\n"
            "        return ''\n"
        )
        # Note: RedisCache doesn't explicitly inherit from Cache,
        # so it won't be counted. This tests that Protocol is detected.
        results = checker.check_premature_seam(code)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].seam_name, "Cache")
        self.assertEqual(results[0].adapter_count, 0)
        self.assertTrue(results[0].is_premature)


# ======================================================================
# check_premature_seam — real seam (2+ adapters)
# ======================================================================


class TestCheckPrematureSeamRealSeam(unittest.TestCase):
    """T5-T6: Real seam detection (2+ implementations)."""

    def test_abc_with_two_impls_is_real_seam(self) -> None:
        """Verify: ABC with 2 concrete implementations is a real seam."""
        checker = YagniChecker()
        code = (
            "from abc import ABC\n"
            "class DataStore(ABC):\n"
            "    pass\n"
            "\n"
            "class SqlStore(DataStore):\n"
            "    pass\n"
            "\n"
            "class FileStore(DataStore):\n"
            "    pass\n"
        )
        results = checker.check_premature_seam(code)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].seam_name, "DataStore")
        self.assertEqual(results[0].adapter_count, 2)
        self.assertFalse(results[0].is_premature)
        self.assertIn("SqlStore", results[0].adapters)
        self.assertIn("FileStore", results[0].adapters)
        self.assertIn("Real seam", results[0].reason)

    def test_abc_with_three_impls_is_real_seam(self) -> None:
        """Verify: ABC with 3 implementations is a real seam."""
        checker = YagniChecker()
        code = (
            "class Handler(ABC):\n"
            "    pass\n"
            "\n"
            "class HttpHandler(Handler):\n"
            "    pass\n"
            "\n"
            "class WebSocketHandler(Handler):\n"
            "    pass\n"
            "\n"
            "class GrpcHandler(Handler):\n"
            "    pass\n"
        )
        results = checker.check_premature_seam(code)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].adapter_count, 3)
        self.assertFalse(results[0].is_premature)


# ======================================================================
# check_premature_seam — @abstractmethod detection
# ======================================================================


class TestCheckPrematureSeamAbstractMethod(unittest.TestCase):
    """T7: @abstractmethod detection (without explicit ABC inheritance)."""

    def test_abstractmethod_makes_class_abstract(self) -> None:
        """Verify: class with @abstractmethod is detected as abstract."""
        checker = YagniChecker()
        code = (
            "from abc import abstractmethod\n"
            "class BaseProcessor:\n"
            "    @abstractmethod\n"
            "    def process(self, data):\n"
            "        pass\n"
            "\n"
            "class CsvProcessor(BaseProcessor):\n"
            "    def process(self, data):\n"
            "        return data\n"
        )
        results = checker.check_premature_seam(code)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].seam_name, "BaseProcessor")
        self.assertEqual(results[0].adapter_count, 1)
        self.assertTrue(results[0].is_premature)


# ======================================================================
# check_premature_seam — syntax error handling
# ======================================================================


class TestCheckPrematureSeamSyntaxError(unittest.TestCase):
    """T8: Syntax error handling."""

    def test_syntax_error_returns_error_result(self) -> None:
        """Verify: code with syntax error returns error result."""
        checker = YagniChecker()
        code = "class Foo(\n"  # incomplete class definition
        results = checker.check_premature_seam(code)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].seam_name, "<syntax_error>")
        self.assertIn("Could not parse", results[0].reason)


# ======================================================================
# check_premature_seam — multiple seams
# ======================================================================


class TestCheckPrematureSeamMultiple(unittest.TestCase):
    """T9: Multiple seams in one file."""

    def test_multiple_abstract_classes(self) -> None:
        """Verify: multiple ABCs are each checked independently."""
        checker = YagniChecker()
        code = (
            "from abc import ABC\n"
            "class Store(ABC):\n"
            "    pass\n"
            "\n"
            "class SqlStore(Store):\n"
            "    pass\n"
            "\n"
            "class FileStore(Store):\n"
            "    pass\n"
            "\n"
            "class Cache(ABC):\n"
            "    pass\n"
            "\n"
            "class RedisCache(Cache):\n"
            "    pass\n"
        )
        results = checker.check_premature_seam(code)
        self.assertEqual(len(results), 2)
        # Store has 2 adapters → real seam
        store_result = next(r for r in results if r.seam_name == "Store")
        self.assertFalse(store_result.is_premature)
        self.assertEqual(store_result.adapter_count, 2)
        # Cache has 1 adapter → premature
        cache_result = next(r for r in results if r.seam_name == "Cache")
        self.assertTrue(cache_result.is_premature)
        self.assertEqual(cache_result.adapter_count, 1)


# ======================================================================
# _get_base_name — helper tests
# ======================================================================


class TestGetBaseName(unittest.TestCase):
    """T10-T12: _get_base_name helper."""

    def test_name_node(self) -> None:
        """Verify: ast.Name returns the id."""
        import ast
        node = ast.Name(id="ABC", ctx=ast.Load())
        self.assertEqual(YagniChecker._get_base_name(node), "ABC")

    def test_attribute_node(self) -> None:
        """Verify: ast.Attribute returns the attr."""
        import ast
        node = ast.Attribute(
            value=ast.Name(id="abc", ctx=ast.Load()),
            attr="ABC",
            ctx=ast.Load(),
        )
        self.assertEqual(YagniChecker._get_base_name(node), "ABC")

    def test_subscript_node_recurses(self) -> None:
        """Verify: ast.Subscript recurses to get the base name."""
        import ast
        node = ast.Subscript(
            value=ast.Name(id="Protocol", ctx=ast.Load()),
            slice=ast.Name(id="T", ctx=ast.Load()),
            ctx=ast.Load(),
        )
        self.assertEqual(YagniChecker._get_base_name(node), "Protocol")


# ======================================================================
# _is_abstract_class — helper tests
# ======================================================================


class TestIsAbstractClass(unittest.TestCase):
    """T13-T15: _is_abstract_class helper."""

    def test_abc_inheritance_is_abstract(self) -> None:
        """Verify: class inheriting from ABC is abstract."""
        import ast
        checker = YagniChecker()
        tree = ast.parse("from abc import ABC\nclass Foo(ABC):\n    pass\n")
        class_node = tree.body[1]  # type: ignore[index]
        self.assertTrue(checker._is_abstract_class(class_node))

    def test_abstractmethod_decorator_is_abstract(self) -> None:
        """Verify: class with @abstractmethod is abstract."""
        import ast
        checker = YagniChecker()
        tree = ast.parse(
            "from abc import abstractmethod\n"
            "class Foo:\n"
            "    @abstractmethod\n"
            "    def bar(self):\n"
            "        pass\n"
        )
        class_node = tree.body[1]  # type: ignore[index]
        self.assertTrue(checker._is_abstract_class(class_node))

    def test_regular_class_is_not_abstract(self) -> None:
        """Verify: regular class is not abstract."""
        import ast
        checker = YagniChecker()
        tree = ast.parse("class Foo:\n    pass\n")
        class_node = tree.body[0]
        self.assertFalse(checker._is_abstract_class(class_node))


# ======================================================================
# Integration — real-world pattern
# ======================================================================


class TestCheckPrematureSeamIntegration(unittest.TestCase):
    """T16: Integration test with realistic code pattern."""

    def test_repository_pattern_with_premature_and_real_seams(self) -> None:
        """Verify: repository pattern with mixed premature/real seams."""
        checker = YagniChecker()
        code = (
            "from abc import ABC, abstractmethod\n"
            "\n"
            "class Repository(ABC):\n"
            "    @abstractmethod\n"
            "    def find_by_id(self, id):\n"
            "        pass\n"
            "    @abstractmethod\n"
            "    def save(self, entity):\n"
            "        pass\n"
            "\n"
            "class SqlRepository(Repository):\n"
            "    def find_by_id(self, id):\n"
            "        return {'id': id}\n"
            "    def save(self, entity):\n"
            "        print('saved')\n"
            "\n"
            "class MongoRepository(Repository):\n"
            "    def find_by_id(self, id):\n"
            "        return {'_id': id}\n"
            "    def save(self, entity):\n"
            "        print('saved')\n"
            "\n"
            "class EventBus(ABC):\n"
            "    @abstractmethod\n"
            "    def publish(self, event):\n"
            "        pass\n"
            "\n"
            "class RedisEventBus(EventBus):\n"
            "    def publish(self, event):\n"
            "        print(event)\n"
        )
        results = checker.check_premature_seam(code)
        self.assertEqual(len(results), 2)

        repo_result = next(r for r in results if r.seam_name == "Repository")
        self.assertEqual(repo_result.adapter_count, 2)
        self.assertFalse(repo_result.is_premature)

        bus_result = next(r for r in results if r.seam_name == "EventBus")
        self.assertEqual(bus_result.adapter_count, 1)
        self.assertTrue(bus_result.is_premature)


if __name__ == "__main__":
    unittest.main()
