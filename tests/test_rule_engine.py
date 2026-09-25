#!/usr/bin/env python3
"""Unit tests for V4.5.20 W1-1 ``scripts/collaboration/rule_engine.py``.

Spec: ``docs/reference/DETERMINISTIC_CONTRACT.md`` §5 (C4–C7) and PRD E2. The
contract names this file as the proof for the four rule clauses, so each test below
names the clause it pins down.

Iron Rules applied:
  1. Documentation-first: the contract and the module were read before this file
     was written; the assertions are the clause text, not a paraphrase of it.
  2. Failure-means-report: real files in a temp dir, real JSON, no Mock. Every
     layer test writes the file it resolves, so a passing test cannot come from a
     stale fixture.
  3. Dimension-completeness: Happy path / Error / Boundary / Config / Side-effect.
  4. Side-effect-verification: the packaged ``system_rules.json`` is actually read
     from disk and asserted to carry the catch-all, rather than assumed present.
  5. User-journey-first: the journey is "I wrote a rule at layer N, why did layer M
     win?" — which is also what ``rules check`` (W1-2) has to answer.
  6. e2e-release-gate: the rule layer is what E1's filter decisions rest on.

The negative half of C7 matters more than the positive half: a protection that a
test only ever observes succeeding is a protection nobody has tried to break. Each
of the three configurable layers gets its own bypass attempt.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.collaboration.rule_engine import (  # noqa: E402
    LAYER_CLI,
    LAYER_PROJECT,
    LAYER_SECURITY,
    LAYER_SYSTEM,
    LAYER_USER,
    SECURITY_GATE,
    SECURITY_PATH_PATTERNS,
    SYSTEM_RULES_FILENAME,
    RuleConfigError,
    RuleSources,
    default_sources,
    load_rules,
    matches,
    resolve,
    security_resolution,
)

# The catch-all every healthy system layer ends with (C6).
_CATCH_ALL: dict = {"pattern": "**", "body": {"review": False, "kind": "unclaimed"}}


class _Layers:
    """A temp directory holding real layer files, one per resolution layer."""

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="devsquad_rules_"))
        self.cli = self.root / "cli.json"
        self.project = self.root / "project.json"
        self.user = self.root / "user.json"
        self.system = self.root / "system.json"
        self.write(self.system, [_CATCH_ALL])

    def write(self, target: Path, rules: list[dict]) -> Path:
        """Write a layer file; returns its path so call sites stay one-liners."""
        target.write_text(json.dumps({"rules": rules}), encoding="utf-8")
        return target

    def sources(self) -> RuleSources:
        """Point all four layers at this temp directory."""
        return RuleSources(cli=self.cli, project=self.project, user=self.user, system=self.system)

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


class T1_LayerOrder(unittest.TestCase):
    """T1: C4 — the four layers, in order, and silent absence."""

    def setUp(self) -> None:
        self.layers = _Layers()

    def tearDown(self) -> None:
        self.layers.cleanup()

    def test_01_cli_layer_wins_over_all_lower_layers(self) -> None:
        """Verify: with all four layers claiming a path, layer 1 wins (C4)."""
        self.layers.write(self.layers.cli, [{"pattern": "**/*.py", "body": {"from": "cli"}}])
        self.layers.write(self.layers.project, [{"pattern": "**/*.py", "body": {"from": "project"}}])
        self.layers.write(self.layers.user, [{"pattern": "**/*.py", "body": {"from": "user"}}])
        settled = resolve("src/app.py", self.layers.sources())
        self.assertEqual(settled.layer, LAYER_CLI)
        self.assertEqual(settled.body, {"from": "cli"})

    def test_02_project_layer_wins_when_no_cli_rule_was_given(self) -> None:
        """Verify: layer 2 wins when layer 1 is absent — the normal case (C4)."""
        self.layers.write(self.layers.project, [{"pattern": "**/*.py", "body": {"from": "project"}}])
        self.layers.write(self.layers.user, [{"pattern": "**/*.py", "body": {"from": "user"}}])
        settled = resolve("src/app.py", self.layers.sources())
        self.assertEqual(settled.layer, LAYER_PROJECT)

    def test_03_user_layer_wins_when_cli_and_project_are_absent(self) -> None:
        """Verify: layer 3 is reached when the two layers above it are missing (C4)."""
        self.layers.write(self.layers.user, [{"pattern": "**/*.py", "body": {"from": "user"}}])
        settled = resolve("src/app.py", self.layers.sources())
        self.assertEqual(settled.layer, LAYER_USER)

    def test_04_system_layer_is_the_fallback(self) -> None:
        """Verify: an unclaimed path resolves to the system catch-all (C6)."""
        settled = resolve("notes.xyz", self.layers.sources())
        self.assertEqual(settled.layer, LAYER_SYSTEM)
        self.assertEqual(settled.pattern, "**")
        self.assertEqual(settled.body, _CATCH_ALL["body"])

    def test_05_absent_files_are_skipped_without_an_error(self) -> None:
        """Verify: a layer path that does not exist yields no rules, not a raise (C4)."""
        self.assertEqual(load_rules(self.layers.cli), ())
        self.layers.write(self.layers.user, [{"pattern": "**/*.py", "body": {"from": "user"}}])
        settled = resolve("src/app.py", self.layers.sources())
        self.assertEqual(settled.layer, LAYER_USER)


class T2_NoMerge(unittest.TestCase):
    """T2: C5 — first match wins, and the result is the winner's rule byte for byte."""

    def setUp(self) -> None:
        self.layers = _Layers()

    def tearDown(self) -> None:
        self.layers.cleanup()

    def test_06_result_is_the_winner_alone_not_a_union(self) -> None:
        """Verify: the losing layer contributes nothing to the resolved body (C5)."""
        self.layers.write(self.layers.cli, [{"pattern": "**/*.py", "body": {"a": 1}}])
        self.layers.write(self.layers.project, [{"pattern": "**/*.py", "body": {"b": 2}}])
        settled = resolve("src/app.py", self.layers.sources())
        self.assertEqual(settled.body, {"a": 1})
        self.assertNotIn("b", settled.body)

    def test_07_specificity_does_not_beat_layer_order(self) -> None:
        """Verify: a narrower pattern lower down still loses to the layer above (C5)."""
        self.layers.write(self.layers.cli, [{"pattern": "**/*.py", "body": {"from": "cli-broad"}}])
        self.layers.write(self.layers.project, [{"pattern": "src/app.py", "body": {"from": "project-exact"}}])
        settled = resolve("src/app.py", self.layers.sources())
        self.assertEqual(settled.body, {"from": "cli-broad"})

    def test_08_rule_order_within_a_layer_decides(self) -> None:
        """Verify: inside one layer the first matching entry wins (C5 'file order')."""
        self.layers.write(
            self.layers.cli,
            [
                {"pattern": "**/*.py", "body": {"position": "first"}},
                {"pattern": "src/app.py", "body": {"position": "second"}},
            ],
        )
        settled = resolve("src/app.py", self.layers.sources())
        self.assertEqual(settled.pattern, "**/*.py")
        self.assertEqual(settled.body, {"position": "first"})

    def test_09_body_is_carried_verbatim(self) -> None:
        """Verify: nested bodies survive resolution unchanged, so no field is lost (C5)."""
        body = {"review": True, "nested": {"deep": [1, 2, 3]}, "flag": False}
        self.layers.write(self.layers.cli, [{"pattern": "src/**", "body": body}])
        settled = resolve("src/app.py", self.layers.sources())
        self.assertEqual(settled.body, body)


class T3_SecurityExemption(unittest.TestCase):
    """T3: C7 — the hardcoded exemption, and three attempts to bypass it."""

    def setUp(self) -> None:
        self.layers = _Layers()

    def tearDown(self) -> None:
        self.layers.cleanup()

    def test_10_cli_include_cannot_pull_a_secret_path_back(self) -> None:
        """Verify: an `include` at the highest layer still loses to the wall (C7)."""
        self.layers.write(self.layers.cli, [{"pattern": "**/.env", "body": {"include": True}}])
        settled = resolve("config/.env", self.layers.sources())
        self.assertEqual(settled.layer, LAYER_SECURITY)

    def test_11_project_layer_cannot_switch_the_protection_off(self) -> None:
        """Verify: a committable rule file cannot disable the secret gate (C7)."""
        self.layers.write(
            self.layers.project,
            [{"pattern": "**/*.pem", "body": {"secret_exclude": False, "review": True}}],
        )
        settled = resolve("certs/server.pem", self.layers.sources())
        self.assertEqual(settled.layer, LAYER_SECURITY)

    def test_12_user_layer_cannot_claim_a_sensitive_path(self) -> None:
        """Verify: a locally writable rule file cannot claim a private key (C7)."""
        self.layers.write(self.layers.user, [{"pattern": "**/.ssh/**", "body": {"review": True}}])
        settled = resolve(".ssh/id_ed25519", self.layers.sources())
        self.assertEqual(settled.layer, LAYER_SECURITY)
        self.assertIn(settled.pattern, SECURITY_PATH_PATTERNS)

    def test_13_every_sensitive_sample_hits_the_wall_and_benign_ones_do_not(self) -> None:
        """Verify: the hardcoded set covers the sensitive paths it names, and only those (C7)."""
        sensitive = (
            ".env",
            "config/.env.local",
            "certs/server.pem",
            "deploy/keys/release.key",
            "id_rsa",
            ".ssh/id_ed25519",
            ".netrc",
            ".npmrc",
            ".git-credentials",
            ".aws/credentials",
            "ops/credentials.json",
            "infra/service-account-prod.json",
        )
        for path in sensitive:
            with self.subTest(path=path):
                self.assertIsNotNone(security_resolution(path))
        for path in ("src/app.py", "README.md", "docs/.environment.md", "keys/README.pem.md"):
            with self.subTest(path=path):
                self.assertIsNone(security_resolution(path))

    def test_14_the_verdict_names_the_gate_and_the_glob_that_fired(self) -> None:
        """Verify: the wall reports C1's gate name so the drop is attributable (C1/C7)."""
        settled = resolve("config/.env", self.layers.sources())
        self.assertEqual(settled.body["gate"], SECURITY_GATE)
        self.assertIn(settled.pattern, SECURITY_PATH_PATTERNS)
        self.assertEqual(settled.origin, "<hardcoded>")


class T4_ConfigErrors(unittest.TestCase):
    """T4: C4 — a present-but-broken layer is an error, never a silent skip."""

    def setUp(self) -> None:
        self.layers = _Layers()

    def tearDown(self) -> None:
        self.layers.cleanup()

    def test_15_malformed_json_is_reported(self) -> None:
        """Verify: unparseable JSON raises instead of dropping the caller's rules (C4)."""
        self.layers.project.write_text("{not json", encoding="utf-8")
        with self.assertRaises(RuleConfigError) as caught:
            load_rules(self.layers.project)
        self.assertIn(str(self.layers.project), str(caught.exception))

    def test_16_missing_rules_list_is_reported(self) -> None:
        """Verify: a JSON file without a 'rules' list is rejected, not treated as empty (C4)."""
        self.layers.project.write_text('{"version": 1}', encoding="utf-8")
        with self.assertRaises(RuleConfigError) as caught:
            resolve("src/app.py", self.layers.sources())
        self.assertIn("'rules' list", str(caught.exception))

    def test_17_entry_without_a_pattern_is_reported(self) -> None:
        """Verify: a rule with no glob is rejected rather than silently never matching (C4)."""
        self.layers.write(self.layers.project, [{"body": {"review": True}}])
        with self.assertRaises(RuleConfigError) as caught:
            resolve("src/app.py", self.layers.sources())
        self.assertIn("string 'pattern'", str(caught.exception))

    def test_18_non_object_body_is_reported(self) -> None:
        """Verify: a body that is not an object is rejected (C5 needs a body to compare)."""
        self.layers.write(self.layers.project, [{"pattern": "**", "body": "review"}])
        with self.assertRaises(RuleConfigError) as caught:
            resolve("src/app.py", self.layers.sources())
        self.assertIn("'body' must be a JSON object", str(caught.exception))

    def test_19_system_layer_without_a_catch_all_is_reported(self) -> None:
        """Verify: losing the catch-all breaks C6, so resolution fails loudly (C6)."""
        self.layers.write(self.layers.system, [{"pattern": "**/*.py", "body": {"review": True}}])
        with self.assertRaises(RuleConfigError) as caught:
            resolve("notes.xyz", self.layers.sources())
        self.assertIn("catch-all", str(caught.exception))

    def test_20_absent_system_layer_is_reported(self) -> None:
        """Verify: a package missing its system layer cannot silently resolve nothing (C6)."""
        sources = RuleSources(
            cli=self.layers.cli,
            project=self.layers.project,
            user=self.layers.user,
            system=self.layers.root / "not-shipped.json",
        )
        with self.assertRaises(RuleConfigError):
            resolve("notes.xyz", sources)


class T5_GlobDialect(unittest.TestCase):
    """T5: C4 — the matching dialect the contract documents for rule authors."""

    def test_21_leading_double_star_may_match_zero_directories(self) -> None:
        """Verify: `**/*.py` covers a top-level file, as the contract promises (C4)."""
        self.assertIs(matches("cli.py", "**/*.py"), True)
        self.assertIs(matches("src/cli.py", "**/*.py"), True)

    def test_22_matching_is_right_anchored(self) -> None:
        """Verify: a bare-name glob matches at any depth (documented dialect) (C4)."""
        self.assertIs(matches("src/cli.py", "*.py"), True)
        self.assertIs(matches("src/cli.py", "src/*.py"), True)

    def test_23_unrelated_paths_do_not_match(self) -> None:
        """Verify: the dialect does not over-match, or every rule would win (C4)."""
        self.assertIs(matches("src/cli.py", "docs/**"), False)
        self.assertIs(matches("src/cli.py", "*.md"), False)

    def test_24_packaged_system_rules_end_in_a_catch_all(self) -> None:
        """Verify: the shipped data file really carries C6's catch-all, last."""
        packaged = Path(_PROJECT_ROOT) / "scripts" / "collaboration" / SYSTEM_RULES_FILENAME
        rules = load_rules(packaged)
        self.assertGreaterEqual(len(rules), 1)
        self.assertEqual(rules[-1].pattern, "**")
        self.assertEqual(resolve("anything.xyz", RuleSources(system=packaged)).layer, LAYER_SYSTEM)


class T6_DefaultSources(unittest.TestCase):
    """T6: C4 — the layer locations callers get without passing anything."""

    def test_25_defaults_are_the_documented_locations(self) -> None:
        """Verify: project/user/system land where the contract says they do (C4)."""
        sources = default_sources(repo_root="/tmp/some-repo")
        self.assertEqual(sources.project, Path("/tmp/some-repo/.devsquad/rule.json"))
        self.assertEqual(sources.user, Path.home() / ".devsquad" / "rule.json")
        self.assertIsNone(sources.cli)
        self.assertEqual(sources.system.name, SYSTEM_RULES_FILENAME)

    def test_26_cli_rule_is_forwarded(self) -> None:
        """Verify: `--rule <path>` becomes layer 1 rather than being ignored (C4)."""
        sources = default_sources(repo_root="/tmp/some-repo", cli_rule="/tmp/explicit.json")
        self.assertEqual(sources.cli, Path("/tmp/explicit.json"))


if __name__ == "__main__":
    unittest.main()
