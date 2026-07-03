#!/usr/bin/env python3
"""Coverage-focused tests for SkillRegistry and SkillEntry.

Targets the previously uncovered lines reported by pytest-cov:
  - SkillEntry.to_dict / from_dict round-trip and unknown-key handling
  - SkillRegistry.register path-traversal rejection and persistence
  - unregister (existing + missing), get, execute (missing skill / no handler / success)
  - search (query / category / tags / confidence sort)
  - propose_from_result, list_skills, get_stats
  - _load (happy path + corrupted file), _save (happy path + OSError path)
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from scripts.collaboration.skill_registry import SkillEntry, SkillRegistry


class TestSkillEntrySerialization(unittest.TestCase):
    """SkillEntry.to_dict / from_dict coverage (lines 37, 62)."""

    def test_to_dict_contains_all_fields(self) -> None:
        skill = SkillEntry(
            skill_id="s1",
            name="deploy",
            description="Deploys the app",
            category="devops",
            version="2.0.0",
            handler="handler.module",
            tags=["cd", "k8s"],
            confidence=0.9,
            usage_count=5,
            last_used="2024-01-01T00:00:00",
            created_at="2024-01-01T00:00:00",
            metadata={"owner": "team-a"},
        )
        d = skill.to_dict()
        self.assertEqual(d["skill_id"], "s1")
        self.assertEqual(d["name"], "deploy")
        self.assertEqual(d["description"], "Deploys the app")
        self.assertEqual(d["category"], "devops")
        self.assertEqual(d["version"], "2.0.0")
        self.assertEqual(d["handler"], "handler.module")
        self.assertEqual(d["tags"], ["cd", "k8s"])
        self.assertEqual(d["confidence"], 0.9)
        self.assertEqual(d["usage_count"], 5)
        self.assertEqual(d["last_used"], "2024-01-01T00:00:00")
        self.assertEqual(d["created_at"], "2024-01-01T00:00:00")
        self.assertEqual(d["metadata"], {"owner": "team-a"})

    def test_from_dict_roundtrip(self) -> None:
        original = SkillEntry(
            skill_id="s2",
            name="review",
            description="Code review",
            category="quality",
            tags=["review"],
            confidence=0.7,
        )
        data = original.to_dict()
        restored = SkillEntry.from_dict(data)
        self.assertEqual(restored.skill_id, original.skill_id)
        self.assertEqual(restored.name, original.name)
        self.assertEqual(restored.description, original.description)
        self.assertEqual(restored.category, original.category)
        self.assertEqual(restored.tags, original.tags)
        self.assertEqual(restored.confidence, original.confidence)

    def test_from_dict_ignores_unknown_keys(self) -> None:
        data = {
            "skill_id": "s3",
            "name": "test",
            "unknown_field": "should be ignored",
            "another_unknown": 123,
        }
        skill = SkillEntry.from_dict(data)
        self.assertEqual(skill.skill_id, "s3")
        self.assertEqual(skill.name, "test")

    def test_from_dict_partial_data_uses_defaults(self) -> None:
        skill = SkillEntry.from_dict({"skill_id": "s4"})
        self.assertEqual(skill.skill_id, "s4")
        self.assertEqual(skill.name, "")
        self.assertEqual(skill.category, "general")
        self.assertEqual(skill.confidence, 0.0)
        self.assertEqual(skill.tags, [])


class TestSkillRegistryRegister(unittest.TestCase):
    """register() path traversal + normal registration (lines 96-103)."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.registry = SkillRegistry(storage_path=self.tmpdir)

    def test_register_returns_skill_id(self) -> None:
        skill = SkillEntry(skill_id="abc", name="my-skill")
        result = self.registry.register(skill)
        self.assertEqual(result, "abc")
        self.assertIn("abc", self.registry.skills)

    def test_register_with_handler_stores_handler(self) -> None:
        skill = SkillEntry(skill_id="h1", name="handler-skill")

        def handler(**kwargs):
            return "ok"

        self.registry.register(skill, handler=handler)
        self.assertIn("h1", self.registry.handlers)

    def test_register_without_handler_does_not_store_handler(self) -> None:
        skill = SkillEntry(skill_id="h2", name="no-handler")
        self.registry.register(skill)
        self.assertNotIn("h2", self.registry.handlers)

    def test_register_rejects_dotdot_in_skill_id(self) -> None:
        skill = SkillEntry(skill_id="../etc/passwd", name="evil")
        with self.assertRaises(ValueError):
            self.registry.register(skill)

    def test_register_rejects_slash_in_skill_id(self) -> None:
        skill = SkillEntry(skill_id="a/b", name="evil")
        with self.assertRaises(ValueError):
            self.registry.register(skill)

    def test_register_rejects_backslash_in_skill_id(self) -> None:
        skill = SkillEntry(skill_id="a\\b", name="evil")
        with self.assertRaises(ValueError):
            self.registry.register(skill)

    def test_register_persists_to_disk(self) -> None:
        skill = SkillEntry(skill_id="persist1", name="persisted")
        self.registry.register(skill)
        registry_file = os.path.join(self.tmpdir, "registry.json")
        self.assertTrue(os.path.exists(registry_file))
        with open(registry_file, encoding="utf-8") as f:
            data = json.load(f)
        self.assertTrue(any(s["skill_id"] == "persist1" for s in data["skills"]))

    def test_duplicate_register_overwrites(self) -> None:
        skill1 = SkillEntry(skill_id="dup", name="first", confidence=0.1)
        self.registry.register(skill1)
        skill2 = SkillEntry(skill_id="dup", name="second", confidence=0.9)
        self.registry.register(skill2)
        self.assertEqual(self.registry.skills["dup"].name, "second")
        self.assertEqual(self.registry.skills["dup"].confidence, 0.9)


class TestSkillRegistryUnregisterAndGet(unittest.TestCase):
    """unregister() + get() (lines 114-119, 130)."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.registry = SkillRegistry(storage_path=self.tmpdir)
        self.skill = SkillEntry(skill_id="rm1", name="removable")
        self.registry.register(self.skill)

    def test_unregister_existing_returns_true(self) -> None:
        self.assertTrue(self.registry.unregister("rm1"))
        self.assertNotIn("rm1", self.registry.skills)

    def test_unregister_removes_handler_too(self) -> None:
        skill = SkillEntry(skill_id="rmh", name="with-handler")

        def handler(**kwargs):
            return None

        self.registry.register(skill, handler=handler)
        self.assertTrue(self.registry.unregister("rmh"))
        self.assertNotIn("rmh", self.registry.handlers)

    def test_unregister_missing_returns_false(self) -> None:
        self.assertFalse(self.registry.unregister("does-not-exist"))

    def test_get_existing_returns_skill(self) -> None:
        result = self.registry.get("rm1")
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "removable")

    def test_get_missing_returns_none(self) -> None:
        self.assertIsNone(self.registry.get("nope"))


class TestSkillRegistryExecute(unittest.TestCase):
    """execute() error paths + success (lines 145-157)."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.registry = SkillRegistry(storage_path=self.tmpdir)

    def test_execute_missing_skill_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.registry.execute("missing")

    def test_execute_skill_without_handler_raises(self) -> None:
        skill = SkillEntry(skill_id="noh", name="no-handler")
        self.registry.register(skill)
        with self.assertRaises(ValueError):
            self.registry.execute("noh")

    def test_execute_invokes_handler_and_updates_usage(self) -> None:
        skill = SkillEntry(skill_id="exec1", name="executable")
        calls: list[dict] = []

        def handler(**kwargs):
            calls.append(kwargs)
            return "result"

        self.registry.register(skill, handler=handler)
        self.assertEqual(skill.usage_count, 0)
        self.assertIsNone(skill.last_used)

        result = self.registry.execute("exec1", foo="bar")
        self.assertEqual(result, "result")
        self.assertEqual(calls, [{"foo": "bar"}])
        self.assertEqual(skill.usage_count, 1)
        self.assertIsNotNone(skill.last_used)

    def test_execute_increments_usage_count_multiple_times(self) -> None:
        skill = SkillEntry(skill_id="exec2", name="multi")

        def handler(**kwargs):
            return None

        self.registry.register(skill, handler=handler)
        self.registry.execute("exec2")
        self.registry.execute("exec2")
        self.registry.execute("exec2")
        self.assertEqual(skill.usage_count, 3)


class TestSkillRegistrySearch(unittest.TestCase):
    """search() query / category / tags / sorting (lines 171-180)."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.registry = SkillRegistry(storage_path=self.tmpdir)
        self.registry.register(SkillEntry(skill_id="a", name="Deploy App", description="deploy to prod", category="devops", tags=["k8s"], confidence=0.5))
        self.registry.register(SkillEntry(skill_id="b", name="Code Review", description="review code", category="quality", tags=["review"], confidence=0.9))
        self.registry.register(SkillEntry(skill_id="c", name="Test Runner", description="run tests", category="quality", tags=["test", "ci"], confidence=0.7))

    def test_search_no_filters_returns_all(self) -> None:
        results = self.registry.search()
        self.assertEqual(len(results), 3)

    def test_search_sorted_by_confidence_desc(self) -> None:
        results = self.registry.search()
        confidences = [r.confidence for r in results]
        self.assertEqual(confidences, sorted(confidences, reverse=True))
        self.assertEqual(results[0].skill_id, "b")

    def test_search_by_category(self) -> None:
        results = self.registry.search(category="quality")
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.category == "quality" for r in results))

    def test_search_by_tags_any_match(self) -> None:
        results = self.registry.search(tags=["ci"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].skill_id, "c")

    def test_search_by_multiple_tags(self) -> None:
        results = self.registry.search(tags=["k8s", "review"])
        self.assertEqual(len(results), 2)
        ids = {r.skill_id for r in results}
        self.assertEqual(ids, {"a", "b"})

    def test_search_by_query_matches_name(self) -> None:
        results = self.registry.search(query="deploy")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].skill_id, "a")

    def test_search_by_query_matches_description_case_insensitive(self) -> None:
        results = self.registry.search(query="REVIEW")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].skill_id, "b")

    def test_search_query_no_match_returns_empty(self) -> None:
        results = self.registry.search(query="nonexistent-term")
        self.assertEqual(results, [])

    def test_search_combined_filters(self) -> None:
        results = self.registry.search(query="run", category="quality", tags=["test"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].skill_id, "c")


class TestSkillRegistryProposeAndList(unittest.TestCase):
    """propose_from_result / list_skills / get_stats (lines 197-231)."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.registry = SkillRegistry(storage_path=self.tmpdir)

    def test_propose_from_result_registers_skill(self) -> None:
        skill = self.registry.propose_from_result(
            name="New Skill",
            description="Does a thing",
            category="general",
            confidence=0.8,
            tags=["new"],
        )
        self.assertIn(skill.skill_id, self.registry.skills)
        self.assertEqual(skill.name, "New Skill")
        self.assertEqual(skill.confidence, 0.8)
        self.assertEqual(skill.tags, ["new"])

    def test_propose_from_result_default_tags_empty(self) -> None:
        skill = self.registry.propose_from_result(name="N", description="D")
        self.assertEqual(skill.tags, [])
        self.assertEqual(skill.category, "")
        self.assertEqual(skill.confidence, 0.0)

    def test_list_skills_returns_dicts(self) -> None:
        self.registry.register(SkillEntry(skill_id="l1", name="one", category="a"))
        self.registry.register(SkillEntry(skill_id="l2", name="two", category="b"))
        result = self.registry.list_skills()
        self.assertEqual(len(result), 2)
        self.assertTrue(all(isinstance(d, dict) for d in result))
        ids = {d["skill_id"] for d in result}
        self.assertEqual(ids, {"l1", "l2"})

    def test_list_skills_filtered_by_category(self) -> None:
        self.registry.register(SkillEntry(skill_id="l1", name="one", category="a"))
        self.registry.register(SkillEntry(skill_id="l2", name="two", category="b"))
        self.registry.register(SkillEntry(skill_id="l3", name="three", category="a"))
        result = self.registry.list_skills(category="a")
        self.assertEqual(len(result), 2)
        self.assertTrue(all(d["category"] == "a" for d in result))

    def test_list_skills_empty_registry(self) -> None:
        self.assertEqual(self.registry.list_skills(), [])

    def test_get_stats_empty_registry(self) -> None:
        stats = self.registry.get_stats()
        self.assertEqual(stats["total_skills"], 0)
        self.assertEqual(stats["categories"], {})
        self.assertEqual(stats["with_handlers"], 0)

    def test_get_stats_with_skills_and_handlers(self) -> None:
        s1 = SkillEntry(skill_id="g1", name="a", category="devops")

        def h(**kwargs):
            return None

        self.registry.register(s1, handler=h)
        self.registry.register(SkillEntry(skill_id="g2", name="b", category="devops"))
        self.registry.register(SkillEntry(skill_id="g3", name="c", category="quality"))
        stats = self.registry.get_stats()
        self.assertEqual(stats["total_skills"], 3)
        self.assertEqual(stats["categories"], {"devops": 2, "quality": 1})
        self.assertEqual(stats["with_handlers"], 1)


class TestSkillRegistryPersistence(unittest.TestCase):
    """_load / _save round-trip + error paths (lines 240-256)."""

    def test_load_restores_skills_from_existing_file(self) -> None:
        tmpdir = tempfile.mkdtemp()
        registry = SkillRegistry(storage_path=tmpdir)
        registry.register(SkillEntry(skill_id="load1", name="loaded", category="x"))
        registry.register(SkillEntry(skill_id="load2", name="second", category="y"))

        # New registry instance loading from same path
        registry2 = SkillRegistry(storage_path=tmpdir)
        self.assertIn("load1", registry2.skills)
        self.assertIn("load2", registry2.skills)
        self.assertEqual(registry2.skills["load1"].name, "loaded")
        self.assertEqual(registry2.skills["load2"].category, "y")

    def test_load_empty_file_does_not_crash(self) -> None:
        tmpdir = tempfile.mkdtemp()
        registry_file = os.path.join(tmpdir, "registry.json")
        with open(registry_file, "w", encoding="utf-8") as f:
            f.write("")
        # Should not raise; just warn and continue with empty registry
        registry = SkillRegistry(storage_path=tmpdir)
        self.assertEqual(len(registry.skills), 0)

    def test_load_corrupted_json_does_not_crash(self) -> None:
        tmpdir = tempfile.mkdtemp()
        registry_file = os.path.join(tmpdir, "registry.json")
        with open(registry_file, "w", encoding="utf-8") as f:
            f.write("{not valid json")
        registry = SkillRegistry(storage_path=tmpdir)
        self.assertEqual(len(registry.skills), 0)

    def test_load_missing_skills_key_does_not_crash(self) -> None:
        tmpdir = tempfile.mkdtemp()
        registry_file = os.path.join(tmpdir, "registry.json")
        with open(registry_file, "w", encoding="utf-8") as f:
            json.dump({"other_key": []}, f)
        registry = SkillRegistry(storage_path=tmpdir)
        self.assertEqual(len(registry.skills), 0)

    def test_save_writes_valid_json_file(self) -> None:
        tmpdir = tempfile.mkdtemp()
        registry = SkillRegistry(storage_path=tmpdir)
        registry.register(SkillEntry(skill_id="sv1", name="saved"))
        registry_file = os.path.join(tmpdir, "registry.json")
        with open(registry_file, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("skills", data)
        self.assertEqual(len(data["skills"]), 1)
        self.assertEqual(data["skills"][0]["skill_id"], "sv1")

    def test_save_handles_non_serializable_metadata(self) -> None:
        """_save catches TypeError when metadata contains non-JSON-serializable data."""
        tmpdir = tempfile.mkdtemp()
        registry = SkillRegistry(storage_path=tmpdir)
        skill = SkillEntry(skill_id="bad", name="bad-meta")

        # Inject a non-serializable object into metadata; to_dict will include it
        # and json.dump will raise TypeError, which _save must swallow.
        skill.metadata = {"bad": object()}
        # Should not raise
        registry.register(skill)
        self.assertIn("bad", registry.skills)


if __name__ == "__main__":
    unittest.main()
