"""Centralized constants for DevSquad collaboration module.

This module collects magic numbers that were previously scattered across
dispatcher.py, enhanced_worker.py, llm_backend.py, llm_retry.py, redis_cache.py,
and other collaboration modules. Centralizing them here makes thresholds and
limits easy to discover, audit, and tune.

Guideline: only move a number here when it represents a tunable threshold,
capacity limit, or default configuration. Pure algorithmic constants (e.g.,
TF-IDF smoothing) stay in their owning module.
"""

# === LLM Backend Defaults (llm_backend.py) ===
DEFAULT_LLM_TIMEOUT_SECONDS = 120.0
DEFAULT_LLM_MAX_TOKENS = 4096
DEFAULT_LLM_TEMPERATURE = 0.7

# === LLM Retry (llm_retry.py, llm_retry_base.py) ===
DEFAULT_LLM_MAX_RETRIES = 3
DEFAULT_LLM_MAX_DELAY_SECONDS = 60.0
DEFAULT_LLM_BASE_DELAY_SECONDS = 1.0

# === Dispatcher (dispatcher.py) ===
DEFAULT_MAX_FIX_ITERATIONS = 3
DEFAULT_COMPRESSION_THRESHOLD_CHARS = 100_000

# === EnhancedWorker (enhanced_worker.py) ===
DEFAULT_EXECUTION_GUARD_MAX_DURATION_SECONDS = 300
DEFAULT_EXECUTION_GUARD_MAX_OUTPUT_TOKENS = 8000
DEFAULT_WORKER_CONFIDENCE = 0.7
DEFAULT_WORKER_MAX_ATTEMPTS = 3
DEFAULT_MAX_INJECTED_RULES = 5

# === Cache (redis_cache.py, llm_cache.py) ===
DEFAULT_CACHE_TTL_SECONDS = 3600
DEFAULT_CACHE_LATENCY_WINDOW = 1000

# === Consensus (consensus.py, models_base.py) ===
# CONSENSUS_THRESHOLDS already defined in models_base.py — re-exported for convenience.
CONSENSUS_VETO_WEIGHT = -1.0
CONSENSUS_ARCHITECT_WEIGHT = 1.5
CONSENSUS_PM_WEIGHT = 1.2
CONSENSUS_DEFAULT_WEIGHT = 1.0
CONSENSUS_SPLIT_LOWER_RATIO = 0.4
CONSENSUS_SPLIT_UPPER_RATIO = 0.6

# === Five-Axis Consensus (dispatch_steps_consensus_mixin.py) ===
FIVE_AXIS_DEFAULT_SCORE = 0.8
FIVE_AXIS_DEFAULT_CONFIDENCE = 0.7
FIVE_AXIS_SECURITY_SCORE = 0.7
FIVE_AXIS_SECURITY_CONFIDENCE = 0.6
FIVE_AXIS_PERFORMANCE_SCORE = 0.7
FIVE_AXIS_PERFORMANCE_CONFIDENCE = 0.6

# === Feedback / Quality Gates (feedback_control_loop.py, dispatch_services.py) ===
DEFAULT_QUALITY_GATE_THRESHOLD = 0.7
DEFAULT_PATTERN_CONFIDENCE_HIGH = 0.95
DEFAULT_PATTERN_CONFIDENCE_LOW = 0.3

# === CI Feedback (ci_feedback_adapter.py) ===
CI_PASS_RATIO = 80
CI_WARN_RATIO = 60

# === Audit / History (audit_logger.py, worker.py) ===
DEFAULT_AUDIT_QUERY_LIMIT = 50
DEFAULT_WORKER_RESULT_LIMIT = 10
