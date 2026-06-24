# Archived Modules

> ⚠️ **Note**: Some files referenced below have been removed. This README is kept for historical reference only.

This directory contains modules that have been archived because they have **no production code references** (only self-references or test/example references).

These modules are kept for historical reference and should not be imported by any active production code.

## Archived Files

### Integration Examples (experimental, never integrated into production)
- `async_integration_example.py` - Async integration example
- `integration_example.py` - Synchronous integration example

### Utility Modules (unused in production)
- `structured_logging.py` - Structured logging
- `code_quality.py` - Code quality checks (was in scripts/)

### Test Files (source-directory tests, not in tests/)
- `adaptive_role_selector_test.py`
- `execution_guard_test.py`
- `feedback_control_loop_test.py`
- `similar_task_recommender_test.py`

## Note

The following modules were previously listed here but have been moved back to the main `scripts/collaboration/` directory:
- `async_coordinator.py`, `async_llm_backend.py`, `async_adapter.py` (async modules, marked as Preview)
- `llm_cache_async.py`, `llm_retry_async.py` (async cache/retry, marked as Preview)
- `redis_cache.py`, `cache_interface.py`, `multi_level_cache.py` (cache modules)

These modules exist in the main directory but are **not yet integrated into the main dispatch pipeline** — they are marked as Preview/Experimental.

## Archived on

2026-06-06
