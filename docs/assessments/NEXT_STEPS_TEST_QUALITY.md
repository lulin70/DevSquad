# Next Steps for Test Quality Improvement

## Remaining Work

### 1. E2E Test Implementation (High Priority)
**Status**: Gap identified, not implemented

**Required actions**:
- Create `tests/e2e/test_complete_dispatch_workflow.py`
- Implement test: user task → role matching → worker execution → report generation
- Add test: multi-worker collaboration with scratchpad exchange
- Add test: failure recovery scenario

**Blockers**:
- Requires LLM backend configuration
- Needs real task test data
- Longer execution time (may need mocking LLM for speed)

### 2. Bug Fixes (High Priority)
**Status**: Bugs detected, not fixed

**Issue 1: Import errors (84 test failures)**
- Missing dependencies: pydantic, requests, Pillow, fastapi, uvicorn, streamlit, httpx, mcp
- Solution: Add pytest markers `@pytest.mark.optional` for tests requiring optional deps
- Update pytest configuration to skip optional tests by default

**Issue 2: E2E test failures (13 errors)**
- Tests require optional packages not installed
- Solution: Add conditional skip decorators

**Issue 3: TestCoverageChecker collection warnings**
- Class has `__init__` constructor
- Solution: Rename class or remove `__init__`

### 3. Test Quality Improvements (Medium Priority)

**Replace mocks with real components**:
- `tests/test_report_formatter.py`: Replace `_MockExecResult` with real Worker results
- `tests/test_dispatch_models.py`: Use real DispatchResult from actual dispatch runs

**Add real-world test data**:
- Load actual task examples from past DevSquad runs
- Test with real Chinese/English/Japanese content

## Estimated Effort

- E2E test implementation: 2-3 hours (requires LLM setup)
- Bug fixes: 1 hour (pytest markers and skips)
- Test quality improvements: 2-4 hours (replace mocks, add real data)

**Total remaining**: 5-8 hours of work

## Completion Criteria

Goal is **complete** when:
- ✅ Test quality audit done
- ✅ Integration tests added (4+ new tests)
- ✅ E2E tests added (3+ new tests covering workflows)
- ✅ All bugs fixed (0 import errors, tests pass or skip gracefully)
- ✅ Test quality improved (reduced mocking, real component usage)

## Current Completion: 50%

- ✅ Audit complete
- ✅ Integration tests added
- ❌ E2E tests missing
- ❌ Bugs not fixed
