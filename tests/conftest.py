"""Shared test-suite helpers for DevSquad.

V4.5.20 P1-2 — environment-scaled performance budgets
-----------------------------------------------------

The suite contains wall-clock performance assertions with an *absolute* budget
(e.g. "1000-line dependency scan < 200 ms"). Those budgets were calibrated on
one developer machine. On CI's shared runners the same operation legitimately
measures several times slower, and the suite went red on a run that contained
**zero** source changes: ``test_dependency_hallucination_checker``
``test_01_scan_1000_lines_under_200ms`` failed with
``AssertionError: 406.46311000000424 not less than 200.0`` while the dev host
measures a median of 40.7 ms for that exact operation (9.9x).

Raising the constant (or widening it until CI went green) would have deleted the
gate. Instead the *criterion* is kept and the budget is made
**environment-scaled**:

    ceiling_ms = budget_ms * max(1.0, reference_now_ms / REFERENCE_MS_DEV)

On the calibration host the factor is ``1.0``, so the ceiling equals the original
budget — the gate is **exactly as strong as before there** — and on a host that
is measured slower the ceiling grows in proportion to that measured slowdown.

Why the control must NOT call the object under test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The control is :func:`reference_workload_ms` — a deterministic, dependency-free
CPU workload that does not touch any DevSquad module. This is deliberate, and it
matches the approved precedent in
``tests/unit/test_scratchpad_history_store.py`` (``_raw_commit_floor_ms``: "it
deliberately does NOT call ``ScratchpadHistoryStore`` ... using the store here
would make the ratio ~1 by construction and the gate toothless").

Using the *same code path* at a smaller input as the control is worse than
toothless — it inverts the gate. Because the regression then inflates the control
exactly as much as the operation, ``ceiling`` grows in lockstep with the
operation and the assertion can no longer fail. Measured on this host with a
constant per-import cost injected into ``security_scan_dependencies`` (a 13.7x
slowdown):

    op(1000 imports) = 556.4 ms   same-code-path control(100) = 64.4 ms
    original gate      : 556.4 < 200.0     -> FAIL (caught)
    same-code-path gate: 556.4 < 2971.4    -> PASS (missed)

With an operation-independent control the same regression still trips: the
reference workload is unaffected, the ceiling stays ~200 ms, and 556.4 > 200.

What the gate is and is not
~~~~~~~~~~~~~~~~~~~~~~~~~~~

* It catches any regression that inflates the measured operation by more than the
  host's measured slowdown — i.e. every absolute/algorithmic regression the
  original budget was there to catch (an O(n^2) rewrite, an extra query per
  write, a cache that stopped caching). Verified per site by an injected
  regression.
* It no longer measures how fast the CI host happens to be, which is the one
  thing the absolute budget was never meant to gate. CI runners are shared VMs;
  their absolute wall-clock is not a stable property.
* The control is a pure-CPU proxy. For I/O-heavy operations it may under-track
  the host, so a small residual risk of a too-tight ceiling remains on a very
  slow host; the reference deliberately over-tracks under coverage
  instrumentation (coverage overhead is proportional to executed Python lines),
  which is the direction CI's unit job runs in.

Calibration host (recorded 2026-09-24, Python 3.12.13, CI-equivalent pins):
``reference_workload_ms()`` median of 15 runs = **0.982 ms**.
"""

from __future__ import annotations

import os
import statistics
import time
from collections.abc import Iterator
from contextlib import contextmanager
from unittest import mock

#: Median milliseconds of :func:`reference_workload_ms` on the calibration host
#: (2026-09-24, Python 3.12.13, CI-equivalent dependency pins). See module
#: docstring.
REFERENCE_WORKLOAD_MS_DEV: float = 0.982

#: Iteration count for :func:`reference_workload_ms` (calibrated to ~1 ms).
_REFERENCE_CALLS: int = 4000

__all__ = [
    "PROVIDER_ENV_VARS",
    "REFERENCE_WORKLOAD_MS_DEV",
    "env_perf_factor",
    "isolated_provider_env",
    "perf_ceiling_ms",
    "reference_workload_ms",
]


def reference_workload_ms(*, calls: int = _REFERENCE_CALLS, runs: int = 3) -> float:
    """Median ms of a deterministic, CPU-bound, dependency-free workload.

    The control for every environment-scaled budget in the suite. It must stay
    independent of the code under test — see the module docstring for why.
    """

    def _workload() -> int:
        acc: dict[str, int] = {}
        total = 0
        for i in range(calls):
            key = f"pkg_{i % 997}_suffix"
            acc[key] = acc.get(key, 0) + 1
            total += len(key)
        return total + len(sorted(acc.items(), key=lambda kv: (-kv[1], kv[0]))[:8])

    samples: list[float] = []
    for _ in range(max(runs, 1)):
        start = time.perf_counter()
        _workload()
        samples.append((time.perf_counter() - start) * 1000.0)
    return statistics.median(samples)


def env_perf_factor() -> float:
    """Dimensionless host slowdown factor; ``1.0`` on the calibration host."""
    return max(1.0, reference_workload_ms() / REFERENCE_WORKLOAD_MS_DEV)


def perf_ceiling_ms(budget_ms: float) -> float:
    """Environment-scaled ceiling for an absolute ``budget_ms``.

    Returns ``budget_ms`` on the calibration host, and ``budget_ms`` scaled by
    the measured host slowdown elsewhere. Units are those of ``budget_ms``
    (milliseconds or seconds — the factor is dimensionless).
    """
    return budget_ms * env_perf_factor()


# ---------------------------------------------------------------------------
# Provider-credential isolation (PRD §6 (8) P2-4)
# ---------------------------------------------------------------------------
#
# CI's runners have no ``.env``, so ``create_backend("auto")`` always builds the
# mock chain there. A developer machine does have one, which silently switches
# any test that creates the ``auto`` chain onto live provider calls — 5 serial
# role votes in the autonomous loop, ~10.7 s per ``generate()`` once a provider
# key is stale, against a 60 s ``--timeout``. Those tests then pass or fail
# depending on the host's ``.env`` and on how loaded the machine is, which is
# exactly what a gate must not depend on. See :func:`isolated_provider_env`.

#: Credentials that make ``create_backend("auto")`` reach a real provider.
PROVIDER_ENV_VARS: tuple[str, ...] = (
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_MODEL",
    "DEVSQUAD_OPENAI_API_KEY",
    "DEVSQUAD_OPENAI_BASE_URL",
    "DEVSQUAD_OPENAI_MODEL",
    "MOKA_API_KEY",
    "MOKA_API_BASE",
    "MOKA_BASE_URL",
    "MOKA_MODEL",
    "ANTHROPIC_API_KEY",
    "DEVSQUAD_ANTHROPIC_API_KEY",
)


@contextmanager
def isolated_provider_env() -> Iterator[None]:
    """Run the block as CI does: no provider credentials, mock LLM chain.

    The variables are *removed*, not blanked — ``create_backend`` treats a
    present-but-empty ``OPENAI_BASE_URL`` as "base_url configured" and fails
    with ``APIConnectionError`` instead of degrading to the mock backend.

    ``llm_backend._load_dotenv`` is disabled for the duration as well. It has a
    once-per-process sentinel, so in a full-suite run it is normally already
    spent by the time these tests execute — but relying on that would make the
    isolation depend on collection order, and on a targeted run
    (``pytest tests/test_autonomous.py``) it would re-read ``.env`` and restore
    every credential removed here.
    """
    saved = {name: os.environ.pop(name) for name in PROVIDER_ENV_VARS if name in os.environ}
    patcher = mock.patch("scripts.collaboration.llm_backend._load_dotenv", lambda: None)
    patcher.start()
    try:
        yield
    finally:
        patcher.stop()
        os.environ.update(saved)
