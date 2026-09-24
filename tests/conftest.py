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

import statistics
import time

#: Median milliseconds of :func:`reference_workload_ms` on the calibration host
#: (2026-09-24, Python 3.12.13, CI-equivalent dependency pins). See module
#: docstring.
REFERENCE_WORKLOAD_MS_DEV: float = 0.982

#: Iteration count for :func:`reference_workload_ms` (calibrated to ~1 ms).
_REFERENCE_CALLS: int = 4000

__all__ = [
    "REFERENCE_WORKLOAD_MS_DEV",
    "env_perf_factor",
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
