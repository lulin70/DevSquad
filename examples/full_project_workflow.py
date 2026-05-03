#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DevSquad V3.5.0-C Full Project Workflow Example

Demonstrates a complete project lifecycle from requirements to deployment
using the FULL mode 11-phase lifecycle.

This example simulates:
  - Real project: Building a REST API service
  - All 11 phases with realistic data
  - Checkpoint persistence for long-running tasks
  - Gate checks at each phase transition

Run:
    cd /Users/lin/trae_projects/DevSquad
    python3 examples/full_project_workflow.py
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ProjectWorkflowDemo:
    """
    Demonstrates a complete project workflow using DevSquad lifecycle.
    """

    def __init__(self, project_name: str = "UserAPI Service"):
        self.project_name = project_name
        self.temp_dir = tempfile.mkdtemp(prefix=f"devsquad_{project_name.replace(' ', '_')}_")
        self.adapter = None
        self.checkpoint_mgr = None

        print(f"🏗️  Initializing project: {self.project_name}")
        print(f"   Working directory: {self.temp_dir}")

    def setup(self):
        """Initialize lifecycle adapter and checkpoint manager."""
        from scripts.collaboration.lifecycle_protocol import FullLifecycleAdapter
        from scripts.collaboration.checkpoint_manager import CheckpointManager

        print("\n⚙️  Setting up lifecycle management...")

        # Create adapter in FULL mode with unified gate engine
        self.adapter = FullLifecycleAdapter(use_unified_gate=True)
        self.adapter.set_task_id(self.project_name)

        # Enable checkpoint integration for state persistence
        self.checkpoint_mgr = CheckpointManager(storage_path=self.temp_dir)
        enabled = self.adapter.enable_checkpoint_integration(
            storage_path=self.temp_dir
        )
        print(f"   ✅ FullLifecycleAdapter created (mode: {self.adapter.get_mode().value})")
        print(f"   ✅ CheckpointManager enabled: {enabled}")
        print(f"   ✅ Task ID: {self.project_name}")

    def run_phase_p1_requirements(self):
        """
        Phase P1: Requirements Analysis

        Gather and document project requirements.
        """
        print("\n" + "=" * 60)
        print("📋 PHASE P1: Requirements Analysis")
        print("=" * 60)

        result = self.adapter.advance_to_phase("P1")
        if not result.success:
            print(f"❌ Failed to start P1: {result.error}")
            return False

        print("\n📝 Gathering requirements...")
        requirements = [
            "REST API for user management",
            "CRUD operations for users",
            "JWT authentication",
            "Input validation",
            "Rate limiting",
            "API documentation (OpenAPI/Swagger)",
        ]
        for i, req in enumerate(requirements, 1):
            print(f"   {i}. {req}")

        print("\n✅ Requirements gathered and documented")
        self.adapter.complete_phase("P1")
        self._save_checkpoint("P1_complete", {
            "requirements_count": len(requirements),
            "artifacts": ["requirements.md"],
        })
        return True

    def run_phase_p2_architecture(self):
        """
        Phase P2: Architecture Design

        Define system architecture and technology choices.
        """
        print("\n" + "=" * 60)
        print("🏛️  PHASE P2: Architecture Design")
        print("=" * 60)

        result = self.adapter.advance_to_phase("P2")
        if not result.success:
            print(f"❌ Failed to start P2: {result.error}")
            return False

        print("\n🔨 Defining architecture decisions...")

        architecture = {
            "framework": "FastAPI (Python)",
            "database": "PostgreSQL + SQLAlchemy ORM",
            "auth": "JWT tokens via python-jose",
            "validation": "Pydantic models",
            "docs": "Swagger UI auto-generated",
            "testing": "pytest + httpx",
        }

        for decision, choice in architecture.items():
            print(f"   • {decision}: {choice}")

        print("\n✅ Architecture documented")
        self.adapter.complete_phase("P2")
        self._save_checkpoint("P2_complete", {
            "architecture": list(architecture.keys()),
            "artifacts": ["architecture.md", "tech_stack.md"],
        })
        return True

    def run_phase_p3_technical_design(self):
        """
        Phase P3: Technical Design

        Create detailed technical specifications.
        """
        print("\n" + "=" * 60)
        print("📐 PHASE P3: Technical Design")
        print("=" * 60)

        result = self.adapter.advance_to_phase("P3")
        if not result.success:
            print(f"❌ Failed to start P3: {result.error}")
            return False

        print("\n✏️  Creating technical specifications...")

        api_endpoints = [
            ("POST", "/api/users", "Create user"),
            ("GET", "/api/users/{id}", "Get user by ID"),
            ("PUT", "/api/users/{id}", "Update user"),
            ("DELETE", "/api/users/{id}", "Delete user"),
            ("POST", "/api/auth/login", "Authenticate"),
            ("POST", "/api/auth/refresh", "Refresh token"),
        ]

        print(f"\n   API Endpoints designed ({len(api_endpoints)} total):")
        for method, path, desc in api_endpoints[:4]:
            print(f"      {method:<6} {path:<25} {desc}")
        print(f"      ... and {len(api_endpoints) - 4} more")

        data_models = ["User", "UserCreate", "UserUpdate", "Token", "TokenData"]
        print(f"\n   Data models: {', '.join(data_models)}")

        print("\n✅ Technical design completed")
        self.adapter.complete_phase("P3")
        self._save_checkpoint("P3_complete", {
            "endpoints": len(api_endpoints),
            "models": len(data_models),
            "artifacts": ["api_spec.yaml", "data_models.md"],
        })
        return True

    def run_optional_phases(self):
        """
        Run optional phases (P4-P6) if needed.

        For this demo, we'll skip them to show the feature.
        """
        print("\n" + "=" * 60)
        print("⚡ OPTIONAL PHASES (P4-P6): Skipping for speed")
        print("=" * 60)

        self.adapter.set_skip_optional(True)
        print("   ℹ️  Set skip_optional=True")

        skipped = []
        for pid in ["P4", "P5", "P6"]:
            result = self.adapter.advance_to_phase(pid)
            if result.new_state.value == "skipped":
                skipped.append(pid)
                print(f"   ⏭️  Skipped {pid} (optional)")

        print(f"\n   ✅ Skipped {len(skipped)} optional phases: {', '.join(skipped)}")

    def run_phase_p7_test_planning(self):
        """
        Phase P7: Test Planning

        Define testing strategy and test cases.
        """
        print("\n" + "=" * 60)
        print("🧪 PHASE P7: Test Planning")
        print("=" * 60)

        result = self.adapter.advance_to_phase("P7")
        if not result.success:
            print(f"❌ Failed to start P7: {result.error}")
            return False

        print("\n📋 Defining test strategy...")

        test_plan = {
            "unit_tests": [
                "Test user creation with valid data",
                "Test user creation with invalid data",
                "Test authentication flow",
                "Test token refresh",
            ],
            "integration_tests": [
                "Test full CRUD cycle",
                "Test auth middleware",
                "Test rate limiting",
            ],
            "coverage_target": 85,
            "test_framework": "pytest",
        }

        print(f"\n   Unit tests planned: {len(test_plan['unit_tests'])}")
        print(f"   Integration tests planned: {len(test_plan['integration_tests'])}")
        print(f"   Coverage target: {test_plan['coverage_target']}%")

        print("\n✅ Test plan ready")
        self.adapter.complete_phase("P7")
        self._save_checkpoint("P7_complete", {
            "unit_tests": test_plan["unit_tests"],
            "integration_tests": test_plan["integration_tests"],
            "coverage_target": test_plan["coverage_target"],
            "artifacts": ["test_plan.md"],
        })
        return True

    def run_phase_p8_implementation(self):
        """
        Phase P8: Implementation

        Write the actual code.
        """
        print("\n" + "=" * 60)
        print("💻 PHASE P8: Implementation")
        print("=" * 60)

        result = self.adapter.advance_to_phase("P8")
        if not result.success:
            print(f"❌ Failed to start P8: {result.error}")
            return False

        print("\n🔧 Implementing features...")

        implementation_tasks = [
            ("main.py", "FastAPI app initialization"),
            ("models.py", "SQLAlchemy models"),
            ("schemas.py", "Pydantic schemas"),
            ("routes/users.py", "User CRUD endpoints"),
            ("routes/auth.py", "Authentication endpoints"),
            ("dependencies.py", "Shared dependencies"),
        ]

        for filename, desc in implementation_tasks:
            print(f"   ✓ Created {filename:<25} ({desc})")

        lines_of_code = 450
        files_created = len(implementation_tasks)
        print(f"\n   📊 Implementation stats:")
        print(f"      Files created: {files_created}")
        print(f"      Lines of code: ~{lines_of_code}")

        print("\n✅ Implementation complete")
        self.adapter.complete_phase("P8")
        self._save_checkpoint("P8_complete", {
            "files": files_created,
            "loc": lines_of_code,
            "artifacts": [f[0] for f in implementation_tasks],
        })
        return True

    def run_phase_p9_testing(self):
        """
        Phase P9: Testing & Validation

        Run tests and validate quality.
        """
        print("\n" + "=" * 60)
        print("🧪 PHASE P9: Testing & Validation")
        print("=" * 60)

        result = self.adapter.advance_to_phase("P9")
        if not result.success:
            print(f"❌ Failed to start P9: {result.error}")
            return False

        print("\n🔬 Running tests...")

        # Simulate test results
        test_results = {
            "total": 42,
            "passed": 40,
            "failed": 1,
            "skipped": 1,
            "coverage": 87.5,
            "duration": "12.3s",
        }

        print(f"\n   📊 Test Results:")
        print(f"      Total:  {test_results['total']}")
        print(f"      Passed: ✅ {test_results['passed']}")
        print(f"      Failed: ❌ {test_results['failed']}")
        print(f"      Skipped: ⏭️  {test_results['skipped']}")
        print(f"      Coverage: {test_results['coverage']}%")
        print(f"      Duration: {test_results['duration']}")

        if test_results["coverage"] >= 85:
            print(f"\n   ✅ Coverage target met! ({test_results['coverage']}% ≥ 85%)")
        else:
            print(f"\n   ⚠️  Coverage below target ({test_results['coverage']}% < 85%)")

        print("\n✅ Testing phase complete")
        self.adapter.complete_phase("P9")
        self._save_checkpoint("P9_complete", test_results)
        return True

    def run_phase_p10_deployment(self):
        """
        Phase P10: Deployment

        Prepare and deploy to production.
        """
        print("\n" + "=" * 60)
        print="🚀 PHASE P10: Deployment"
        print("=" * 60)

        result = self.adapter.advance_to_phase("P10")
        if not result.success:
            print(f"❌ Failed to start P10: {result.error}")
            return False

        print("\n📦 Preparing deployment...")

        deployment_steps = [
            "Build Docker image",
            "Run security scans",
            "Push to registry",
            "Deploy to staging",
            "Run smoke tests",
            "Promote to production",
            "Verify health checks",
        ]

        for step in deployment_steps:
            print(f"   ✓ {step}")

        deployment_info = {
            "environment": "production",
            "url": "https://api.example.com/v1",
            "version": "1.0.0",
            "docker_image": "user-api:v1.0.0",
        }

        print(f"\n   🎉 Deployment successful!")
        print(f"      URL: {deployment_info['url']}")
        print(f"      Version: {deployment_info['version']}")

        print("\n✅ Deployment complete")
        self.adapter.complete_phase("P10")
        self._save_checkpoint("P10_complete", deployment_info)
        return True

    def _save_checkpoint(self, label: str, metadata: dict):
        """Save checkpoint with additional metadata."""
        if self.checkpoint_mgr:
            cp = self.checkpoint_mgr.create_checkpoint_from_lifecycle(
                task_id=self.project_name,
                protocol=self.adapter,
            )
            if cp:
                cp.outputs[label] = metadata
                self.checkpoint_mgr.save_checkpoint(cp)
                print(f"   💾 Checkpoint saved: {cp.checkpoint_id}")

    def show_final_status(self):
        """Display final project status."""
        print("\n\n" + "=" * 60)
        print("🎊 PROJECT WORKFLOW COMPLETE!")
        print("=" * 60)

        status = self.adapter.get_status()
        progress = self.adapter.get_execution_progress()

        print(f"\n📈 Final Status:")
        print(f"   Project: {self.project_name}")
        print(f"   Mode: {status.mode.value}")
        print(f"   Progress: {status.progress_percent:.1f}%")
        print(f"   Phases completed: {len(status.completed_phases)}/{progress['total_phases']}")
        print(f"   Completed phases: {', '.join(status.completed_phases)}")

        print(f"\n📋 Phase Summary:")
        for pinfo in progress["phases"]:
            icon = "✅" if pinfo["completed"] else "⏭️" if pinfo["state"] == "skipped" else "❌"
            print(f"   {icon} {pinfo['phase_id']}: {pinfo['name']:<20} [{pinfo['state'].upper()}]")

        print(f"\n💾 Persistence:")
        print(f"   State saved: Yes")
        print(f"   Working dir: {self.temp_dir}")

        # List saved checkpoints
        checkpoints = self.checkpoint_mgr.list_checkpoints(task_id=self.project_name)
        if checkpoints:
            print(f"   Checkpoints created: {len(checkpoints)}")


def main():
    """Run full project workflow demo."""
    print("🚀 DevSquad V3.5.0-C Full Project Workflow Example")
    print("=" * 60)
    print("Simulating complete lifecycle: UserAPI Service")
    print()

    demo = ProjectWorkflowDemo(project_name="UserAPI Service")

    try:
        # Setup
        demo.setup()

        # Run all phases
        phases = [
            ("P1: Requirements", demo.run_phase_p1_requirements),
            ("P2: Architecture", demo.run_phase_p2_architecture),
            ("P3: Technical Design", demo.run_phase_p3_technical_design),
            ("Optional Phases", demo.run_optional_phases),
            ("P7: Test Planning", demo.run_phase_p7_test_planning),
            ("P8: Implementation", demo.run_phase_p8_implementation),
            ("P9: Testing", demo.run_phase_p9_testing),
            ("P10: Deployment", demo.run_phase_p10_deployment),
        ]

        completed = []
        failed = []

        for name, phase_func in phases:
            try:
                success = phase_func()
                if success:
                    completed.append(name)
                else:
                    failed.append(name)
            except Exception as e:
                print(f"\n❌ Error in {name}: {e}")
                failed.append(name)

        # Show final status
        demo.show_final_status()

        print(f"\n\n✅ Workflow Summary:")
        print(f"   Completed: {len(completed)}/{len(phases)} phases")
        print(f"   Failed: {len(failed)} phases")
        if failed:
            print(f"   Failed phases: {', '.join(failed)}")

        print("\n" + "=" * 60)
        print("🎉 Demo completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Cleanup temp directory
        if hasattr(demo, 'temp_dir') and Path(demo.temp_dir).exists():
            # Uncomment to clean up: shutil.rmtree(demo.temp_dir)
            pass


if __name__ == "__main__":
    main()
