#!/usr/bin/env python3
"""
No-secrets-in-repo scanner (V4.5.2 section 8.4 - User Decision CI guard).

Scans the project tree for plaintext API keys and credentials. Fails the
build if any are found (except in explicit mock-placeholder files).

User decision (carrymem):
  "LLM API Key is OK in local environment, but MUST NOT be exposed in code,
   docs, config files, or anything pushed to Git or remote servers."

Scan scope:
  - scripts/ (production code)
  - docs/ (documentation, release notes)
  - tests/ (test fixtures; tests/fakes/ is excluded)
  - Extensions: .py .md .yaml .yml .json .toml .sh .bash .txt .cfg .ini .env .example

Patterns detected (real-world key prefixes):
  - OpenAI:    sk-[A-Za-z0-9]{20,}
  - Anthropic: sk-ant-[A-Za-z0-9_-]{20,}
  - Groq:      gsk_[A-Za-z0-9]{20,}
  - Google:    AIza[0-9A-Za-z_-]{35}
  - GitHub:    ghp_ gho_ ghu_ ghs_ ghr_ (36 chars)
  - Slack:     xox[abprs]-
  - AWS:       AKIA[0-9A-Z]{16}

Excluded paths (allow-list):
  - tests/fakes/**            (mock placeholders)
  - tests/security/test_no_secrets_in_repo.py (this file)
  - docs/_archive/**          (historical)
  - .git/  __pycache__/  .pytest_cache/  .venv/  node_modules/  .devsquad_data/

Excluded placeholder patterns:
  - sk-test-*, sk-fake-*, sk-mock-*, sk-placeholder-*, sk-example-*
  - fake_key, mock_key, your-api-key, <YOUR_KEY>, <YOUR_API_KEY>
  - ${OPENAI_API_KEY}, ${MOKA_API_KEY}, etc.
  - os.environ['OPENAI_API_KEY'], os.environ.get('MOKA_API_KEY')
  - process.env.OPENAI_API_KEY

CI integration:
  Add to .github/workflows/test.yml:
    - name: No secrets in repo
      run: pytest tests/security/test_no_secrets_in_repo.py -v
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = Path(HERE).parent.parent  # tests/security/ -> project root

pytestmark = pytest.mark.security


# === Secret patterns (real-world key prefixes) ===

SECRET_PATTERNS: list[tuple[str, "re.Pattern[str]"]] = [
    ("openai", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("anthropic", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b")),
    ("anthropic-alt", re.compile(r"\bsk-ant-api03-[A-Za-z0-9_\-]{20,}\b")),
    ("groq", re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b")),
    ("google", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("github-token", re.compile(r"\bghp_[A-Za-z0-9]{36}\b")),
    ("github-oauth", re.compile(r"\bgho_[A-Za-z0-9]{36}\b")),
    ("github-user", re.compile(r"\bghu_[A-Za-z0-9]{36}\b")),
    ("github-server", re.compile(r"\bghs_[A-Za-z0-9]{36}\b")),
    ("github-refresh", re.compile(r"\bghr_[A-Za-z0-9]{36}\b")),
    ("slack", re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}\b")),
    ("aws-access", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
]


# === Allow-list for explicit placeholder/mock keys ===

PLACEHOLDER_PATTERNS: list["re.Pattern[str]"] = [
    re.compile(r"sk-test", re.IGNORECASE),
    re.compile(r"sk-fake", re.IGNORECASE),
    re.compile(r"sk-mock", re.IGNORECASE),
    re.compile(r"sk-placeholder", re.IGNORECASE),
    re.compile(r"sk-example", re.IGNORECASE),
    re.compile(r"fake.?key", re.IGNORECASE),
    re.compile(r"mock.?key", re.IGNORECASE),
    re.compile(r"your.?api.?key", re.IGNORECASE),
    re.compile(r"<YOUR.?KEY>", re.IGNORECASE),
    re.compile(r"\$\{.*KEY.*\}"),
    re.compile(r"\$\(.*KEY.*\)"),
    re.compile(r"\{\{.*KEY.*\}\}"),
    re.compile(r"os\.environ\[.*KEY.*\]"),
    re.compile(r"os\.getenv\(.*KEY.*\)"),
    re.compile(r"\.env\.example"),
    re.compile(r"process\.env\.", re.IGNORECASE),
    # Recognizable mock sequences (≥20 alphanumeric chars after sk-)
    re.compile(r"sk-1234567890"),
    re.compile(r"sk-a{10,}", re.IGNORECASE),
    re.compile(r"sk-s{10,}", re.IGNORECASE),
    re.compile(r"AKIAIOSFODNN7EXAMPLE", re.IGNORECASE),  # AWS docs example
]


# === Scan paths and exclusions ===

SCAN_DIRS: list[str] = [
    "scripts",
    "docs",
    "tests",
]

SCAN_EXTENSIONS: tuple[str, ...] = (
    ".py", ".md", ".yaml", ".yml", ".json", ".toml",
    ".sh", ".bash", ".txt", ".cfg", ".ini", ".env", ".example",
)

EXCLUDE_PATH_PATTERNS: list["re.Pattern[str]"] = [
    re.compile(r"\.git/"),
    re.compile(r"__pycache__/"),
    re.compile(r"\.pytest_cache/"),
    re.compile(r"\.venv/"),
    re.compile(r"node_modules/"),
    re.compile(r"\.devsquad_data/"),
    re.compile(r"docs/_archive/"),
    # This test file contains patterns; allow it
    re.compile(r"tests/security/test_no_secrets_in_repo\.py$"),
    # tests/fakes/ contains intentional mock placeholders
    re.compile(r"tests/fakes/"),
    # Real LLM tests intentionally use fake-looking keys to avoid real key leaks
    re.compile(r"tests/external/test_real_llm\.py$"),
    # External test scripts in trae_self_improvement (out of repo scope)
    re.compile(r"trae_self_improvement/.*test_moka_glm\.py$"),
    # Test fixture files that intentionally use mock key strings (smoke tests)
    re.compile(r"tests/test_secret_patterns\.py$"),
    re.compile(r"tests/test_content_cache\.py$"),
    re.compile(r"tests/test_audit_logger\.py$"),
    re.compile(r"tests/test_input_validator_sensitive\.py$"),
    re.compile(r"tests/test_two_stage_review_gate\.py$"),
    # Red-team / attack fixture tests use deliberately key-shaped strings
    re.compile(r"tests/security/red_team\.py$"),
    re.compile(r"tests/security/test_output_validator_redteam\.py$"),
    re.compile(r"tests/e2e/test_user_stories_skeleton\.py$"),
    # Analysis docs (historical) intentionally include sk-... example strings
    re.compile(r"docs/analysis/.*\.md$"),
]


# === Scan engine ===

SecretHit = tuple[str, str, str, int]  # (kind, file, snippet, line_no)


def _is_excluded_path(rel_path: str) -> bool:
    """Return True if path is in the exclusion allow-list."""
    for pat in EXCLUDE_PATH_PATTERNS:
        if pat.search(rel_path):
            return True
    return False


def _is_placeholder(text: str) -> bool:
    """Return True if the matched secret line is an explicit placeholder."""
    for pat in PLACEHOLDER_PATTERNS:
        if pat.search(text):
            return True
    return False


def _should_scan_file(path: Path) -> bool:
    """Return True if the file extension is in scan scope."""
    return path.suffix.lower() in SCAN_EXTENSIONS


def scan_file(path: Path) -> list[SecretHit]:
    """Scan a single file for secret patterns.

    Returns:
        List of (kind, file, snippet, line_no) tuples.
    """
    hits: list[SecretHit] = []
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError):
        return hits

    for line_no, line in enumerate(content.splitlines(), start=1):
        for kind, pattern in SECRET_PATTERNS:
            for match in pattern.finditer(line):
                if _is_placeholder(line):
                    continue
                snippet = match.group(0)
                hits.append((kind, str(path), snippet, line_no))
    return hits


def scan_repo(root: Path = PROJECT_ROOT) -> list[SecretHit]:
    """Scan the project tree. Return all SecretHits found."""
    all_hits: list[SecretHit] = []
    for scan_dir in SCAN_DIRS:
        dir_path = root / scan_dir
        if not dir_path.exists():
            continue
        for path in dir_path.rglob("*"):
            if not path.is_file():
                continue
            if not _should_scan_file(path):
                continue
            rel_path = str(path.relative_to(root))
            if _is_excluded_path(rel_path):
                continue
            hits = scan_file(path)
            all_hits.extend(hits)
    return all_hits


# ---------------------------------------------------------------------------
# T1 - No plaintext keys in code/docs
# ---------------------------------------------------------------------------


class TestT1CodeNoPlaintextKey:
    """T1: sk-[A-Za-z0-9]{20,} in code/docs -> 0 hits (clean fixture)."""

    def test_clean_fixture_returns_no_hits(self, tmp_path):
        """A clean fixture directory with no secrets -> empty hit list."""
        clean_dir = tmp_path / "clean"
        clean_dir.mkdir()
        (clean_dir / "ok.py").write_text(
            "api_key = os.environ['OPENAI_API_KEY']\n",
            encoding="utf-8",
        )
        (clean_dir / "config.md").write_text(
            "Set OPENAI_API_KEY in your environment.\n",
            encoding="utf-8",
        )

        hits: list[SecretHit] = []
        for path in clean_dir.rglob("*"):
            if path.is_file() and _should_scan_file(path):
                hits.extend(scan_file(path))
        assert hits == []

    def test_real_openai_key_detected(self, tmp_path):
        """A real-looking sk-... string IS detected."""
        bad = tmp_path / "leak.py"
        bad.write_text(
            'api_key = "sk-abcdefghijklmnopqrstuvwx"\n',
            encoding="utf-8",
        )
        hits = scan_file(bad)
        assert len(hits) >= 1
        assert hits[0][0] == "openai"

    def test_real_anthropic_key_detected(self, tmp_path):
        """Anthropic sk-ant-... keys are detected."""
        bad = tmp_path / "leak.py"
        bad.write_text(
            'key = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234567890abcdef"\n',
            encoding="utf-8",
        )
        hits = scan_file(bad)
        assert any(h[0] == "anthropic" or h[0] == "anthropic-alt" for h in hits)

    def test_real_github_token_detected(self, tmp_path):
        """GitHub ghp_ tokens detected."""
        bad = tmp_path / "leak.txt"
        bad.write_text(
            "GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz0123456789\n",
            encoding="utf-8",
        )
        hits = scan_file(bad)
        assert any(h[0] == "github-token" for h in hits)

    def test_full_repo_scan_no_secrets(self):
        """Full repo scan must produce 0 hits (allow-listed placeholders OK)."""
        hits = scan_repo()
        if hits:
            report_lines = ["Found potential secrets in repo:"]
            for kind, file, snippet, line_no in hits[:20]:
                report_lines.append(
                    f"  [{kind}] {file}:{line_no}: {snippet[:32]}..."
                )
            report = "\n".join(report_lines)
            pytest.fail(f"{len(hits)} potential secret(s) found:\n{report}")


# ---------------------------------------------------------------------------
# T2 - Mock placeholders allowed
# ---------------------------------------------------------------------------


class TestT2MockPlaceholderAllowed:
    """T2: sk-test-xxx / fake_key / mock_key / <YOUR_API_KEY> / ${...} allowed."""

    @pytest.mark.parametrize(
        "snippet",
        [
            "sk-test-abcdefghijklmnopqrstuvwxyz",
            "sk-fake-1234567890abcdefghij",
            "sk-mock-placeholder-key",
            "sk-example-key-abcdefghij",
            "sk-placeholder-1234567890",
            "fake_key_abcdefghij",
            "mock_key_abcdefghij",
            "your-api-key-here",
            "${OPENAI_API_KEY}",
            "${MOKA_API_KEY}",
            "{{ api_key }}",
            "os.environ['OPENAI_API_KEY']",
            'os.environ.get("MOKA_API_KEY")',
            "process.env.OPENAI_API_KEY",
        ],
    )
    def test_placeholder_not_detected(self, snippet, tmp_path):
        """All explicit placeholder patterns should be allowed."""
        f = tmp_path / "fixture.py"
        f.write_text(f"value = '{snippet}'\n", encoding="utf-8")
        hits = scan_file(f)
        assert hits == [], f"placeholder {snippet!r} should be allowed"

    def test_excluded_paths_ignored(self):
        """Tests/fakes/, .git/, __pycache__/ are excluded."""
        assert _is_excluded_path("tests/fakes/fake.py") is True
        assert _is_excluded_path("scripts/leak.py") is False
        assert _is_excluded_path(".git/config") is True
        assert _is_excluded_path("__pycache__/foo.pyc") is True


# ---------------------------------------------------------------------------
# T3 - Documentation and config also scanned
# ---------------------------------------------------------------------------


class TestT3DocsNoKeyPrefix:
    """T3: docs/config/.md/.yaml scanned; .env.example with placeholders OK."""

    def test_markdown_doc_scanned(self, tmp_path):
        """.md files are scanned (docs/ can leak keys via examples)."""
        bad = tmp_path / "README.md"
        bad.write_text(
            "# Setup\n\nSet `OPENAI_API_KEY=sk-xyzwqrstuvwxabcd12345` in your .env\n",
            encoding="utf-8",
        )
        hits = scan_file(bad)
        assert any(h[0] == "openai" for h in hits)

    def test_yaml_config_scanned(self, tmp_path):
        """.yaml/.yml configs are scanned."""
        bad = tmp_path / "config.yaml"
        bad.write_text(
            "openai:\n  api_key: sk-xyzwqrstuvwxabcd12345\n",
            encoding="utf-8",
        )
        hits = scan_file(bad)
        assert any(h[0] == "openai" for h in hits)

    def test_json_config_scanned(self, tmp_path):
        """.json configs are scanned."""
        bad = tmp_path / "config.json"
        bad.write_text(
            '{"openai_key": "sk-xyzwqrstuvwxabcd12345"}\n',
            encoding="utf-8",
        )
        hits = scan_file(bad)
        assert any(h[0] == "openai" for h in hits)

    def test_env_example_allowed(self, tmp_path):
        """.env.example with placeholders is allowed."""
        f = tmp_path / ".env.example"
        f.write_text(
            "OPENAI_API_KEY=your-api-key-here\n"
            "MOKA_API_KEY=${MOKA_API_KEY}\n"
            "ANTHROPIC_API_KEY=your-anthropic-api-key\n",
            encoding="utf-8",
        )
        hits = scan_file(f)
        assert hits == []


# ---------------------------------------------------------------------------
# Smoke test - module loadable
# ---------------------------------------------------------------------------


class TestSmoke:
    def test_patterns_loaded(self):
        """SECRET_PATTERNS has at least 5 key prefixes."""
        assert len(SECRET_PATTERNS) >= 5

    def test_placeholders_loaded(self):
        """PLACEHOLDER_PATTERNS covers common placeholder forms."""
        assert len(PLACEHOLDER_PATTERNS) >= 10

    def test_exclusions_loaded(self):
        """EXCLUDE_PATH_PATTERNS excludes obvious non-source directories."""
        assert len(EXCLUDE_PATH_PATTERNS) >= 5

    def test_scan_dirs_loaded(self):
        """SCAN_DIRS covers scripts/docs/tests."""
        assert "scripts" in SCAN_DIRS
        assert "docs" in SCAN_DIRS
        assert "tests" in SCAN_DIRS

    def test_scan_extensions_loaded(self):
        """SCAN_EXTENSIONS covers common source/config extensions."""
        assert ".py" in SCAN_EXTENSIONS
        assert ".md" in SCAN_EXTENSIONS
        assert ".yaml" in SCAN_EXTENSIONS
        assert ".json" in SCAN_EXTENSIONS
