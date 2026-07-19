#!/usr/bin/env python3
"""Unit tests for workflow_engine.py main class.

Covers WorkflowEngine.__init__ — storage path creation, attribute
initialization, and default configuration.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pytest

from scripts.collaboration.checkpoint_manager import CheckpointManager
from scripts.collaboration.workflow_engine import WorkflowEngine
from scripts.collaboration.workflow_engine_base import WorkflowDefinition, WorkflowInstance

pytestmark = pytest.mark.unit



class TestWorkflowEngineInit(unittest.TestCase):
    """WorkflowEngine.__init__ tests."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.storage_path = str(Path(self.tmpdir) / "workflows")

    def test_creates_storage_path(self) -> None:
        engine = WorkflowEngine(storage_path=self.storage_path)
        self.assertTrue(engine.storage_path.exists())
        self.assertTrue(engine.storage_path.is_dir())

    def test_initializes_definitions(self) -> None:
        engine = WorkflowEngine(storage_path=self.storage_path)
        self.assertEqual(engine.definitions, {})

    def test_initializes_instances(self) -> None:
        engine = WorkflowEngine(storage_path=self.storage_path)
        self.assertEqual(engine.instances, {})

    def test_initializes_executors(self) -> None:
        engine = WorkflowEngine(storage_path=self.storage_path)
        self.assertEqual(engine.executors, {})

    def test_checkpoint_manager_created(self) -> None:
        engine = WorkflowEngine(storage_path=self.storage_path)
        self.assertIsInstance(engine.checkpoint_manager, CheckpointManager)

    def test_default_checkpoint_interval(self) -> None:
        engine = WorkflowEngine(storage_path=self.storage_path)
        self.assertEqual(engine.checkpoint_interval, 2)

    def test_coordinator_and_dispatcher_none(self) -> None:
        engine = WorkflowEngine(storage_path=self.storage_path)
        self.assertIsNone(engine.coordinator)
        self.assertIsNone(engine.dispatcher)

    def test_coordinator_passed_through(self) -> None:
        coordinator = object()
        engine = WorkflowEngine(storage_path=self.storage_path, coordinator=coordinator)
        self.assertIs(engine.coordinator, coordinator)

    def test_dispatcher_passed_through(self) -> None:
        dispatcher = object()
        engine = WorkflowEngine(storage_path=self.storage_path, dispatcher=dispatcher)
        self.assertIs(engine.dispatcher, dispatcher)

    def test_default_storage_path(self) -> None:
        engine = WorkflowEngine()
        self.assertIsInstance(engine.storage_path, Path)
        self.assertTrue(engine.storage_path.exists())

    def test_storage_path_creates_nested_dirs(self) -> None:
        nested_path = str(Path(self.tmpdir) / "a" / "b" / "c" / "workflows")
        engine = WorkflowEngine(storage_path=nested_path)
        self.assertTrue(engine.storage_path.exists())

    def test_definitions_is_correct_type(self) -> None:
        engine = WorkflowEngine(storage_path=self.storage_path)
        self.assertIsInstance(engine.definitions, dict)

    def test_instances_is_correct_type(self) -> None:
        engine = WorkflowEngine(storage_path=self.storage_path)
        self.assertIsInstance(engine.instances, dict)

    def test_can_add_definition_and_instance(self) -> None:
        engine = WorkflowEngine(storage_path=self.storage_path)
        defn = WorkflowDefinition(workflow_id="wf-1", name="Test")
        engine.definitions[defn.workflow_id] = defn
        inst = WorkflowInstance(instance_id="inst-1", workflow_id="wf-1")
        engine.instances[inst.instance_id] = inst
        self.assertIn("wf-1", engine.definitions)
        self.assertIn("inst-1", engine.instances)


if __name__ == "__main__":
    unittest.main()
