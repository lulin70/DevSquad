#!/usr/bin/env bash
# Local acceptance entry point — the local run whose verdict is comparable to CI's.
#
# Why this exists (PRD §6 (8) P2-4)
# ---------------------------------
# CI's `test` job and `release-e2e`'s `final-gate` job inject no provider
# credentials, so `create_backend("auto")` always builds the mock chain there. A
# developer machine has a `.env`, which moves the very same code onto live
# provider calls: the autonomous loop alone votes for 5 roles serially, and one
# `generate()` measured 10.68 s once the Moka credential went stale (HTTP 401 +
# 3 retries with backoff). Four tests then passed or failed depending on host
# credentials and machine load, which is the one thing a gate must not do.
#
# Run this script, not a bare `pytest`, whenever the local result is meant to be
# the release criterion.
#
# Why blank rather than unset
# ---------------------------
# The root `conftest.py` re-injects every `.env` key that is *missing* from the
# environment, so `unset` here would simply let `.env` put the credentials
# straight back. Present-but-empty is what defeats the re-injection, and an empty
# credential is what makes each backend degrade to `MockBackend`.
#
# Only credentials are blanked. `*_BASE_URL` / `*_MODEL` are deliberately left
# alone: an empty base URL does not read as "unset" to the OpenAI SDK, it reads
# as "configured, and pointing nowhere", which yields connection errors instead
# of a mock fallback.
#
# Scope
# -----
# Mirrors `release-e2e.yml`'s `final-gate` step "Run all unit + integration +
# contract (no external)" literally, including its exclusions. The `e2e` scope is
# deliberately excluded: `test.yml`'s `e2e` job *does* inject
# `DEVSQUAD_OPENAI_*` / `DEVSQUAD_ANTHROPIC_*`, and `release-e2e.yml`'s
# `real-llm-e2e` job additionally injects `MOKA_*`. Both are keyful on CI, so
# mirroring them here would be misleading.
#
# The one intentional deviation is `-p no:randomly`: pytest-randomly is installed
# locally but not on CI, and CI therefore always runs in collection order. The
# flag pins local order to it.
#
# Usage:
#   scripts/acceptance_local.sh
#   PYTHON=python3 scripts/acceptance_local.sh
set -euo pipefail

cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-.venv/bin/python}"

# Credentials blanked for this run — the same five as PRD §6 (9)'s proven
# command, which yielded `9345 passed, 2 skipped`.
CREDENTIALS=(
    OPENAI_API_KEY
    DEVSQUAD_OPENAI_API_KEY
    MOKA_API_KEY
    ANTHROPIC_API_KEY
    DEVSQUAD_ANTHROPIC_API_KEY
)

for name in "${CREDENTIALS[@]}"; do
    value=""
    printf -v "$name" '%s' "$value"
    export "$name"
done

echo "=== provider credentials (blanked for this run) ==="
for name in "${CREDENTIALS[@]}"; do
    value="${!name}"
    echo "  ${name}: ${#value} chars${value:+  <NON-EMPTY — isolation failed!>}"
done
echo

echo "=== keyless-equivalent suite (mirrors release-e2e.yml final-gate) ==="
"$PYTHON" -m pytest tests/unit/ tests/integration/ tests/contract/ \
    tests/test_*.py tests/security/ \
    --ignore=tests/e2e \
    --ignore=tests/external \
    -q --tb=short --timeout=60 -p no:randomly