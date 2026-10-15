# Audit Report: Per-File Correctness Audit

Generated: 2026-09-02
Scope: All Python source files in the TalentLens (JEXA-AI) repository

## Summary

| Metric | Count |
|--------|-------|
| Total Python files audited | 88 |
| Syntax errors (py_compile) | 0 |
| Files with ruff errors | 88 |
| Total ruff errors | 426 |
| Fixable ruff errors | 251 |
| Files with mypy errors | 50 |
| Total mypy errors | 138 |
| Files with mypy clean | 38 |
| Import failures | 0 |
| Runtime import failures | 0 |

## Audit Methodology

1. **Syntax**: `python -m py_compile <file>` — all 88 files passed
2. **Lint**: `ruff check <file>` — 426 total errors, 251 auto-fixable
3. **Types**: `mypy --ignore-missing-imports <file>` — 138 errors across 50 files
4. **Import**: `importlib.import_module()` for all modules — all 88 files imported successfully with proper PYTHONPATH
5. **Runtime**: Gateway FastAPI app imports successfully; all service `main.py` modules import without errors

## Key Findings

### Lint Errors (426 total)
- **UP042**: 14 instances — `str, Enum` should be `enum.StrEnum` (Python 3.11+)
- **UP045**: 16 instances — Use `X | None` instead of `Optional[X]`
- **UP006**: 2 instances — Use `list` instead of `List` for type annotation
- **F401**: 8 instances — Unused imports
- **I001**: 11 instances — Import block sorting/formatting
- **B905**: 2 instances — `zip()` without explicit `strict=` parameter
- **B007**: 1 instance — Unused loop variable
- **F841**: 2 instances — Unused local variables
- **F541**: 1 instance — f-string without placeholders
- **E741**: 1 instance — Ambiguous variable name `l`
- **F821**: 1 instance — Undefined name `Any`
- **SIM102**: 1 instance — Nested if statements
- **SIM105**: 1 instance — Use `contextlib.suppress(Exception)`
- **UP015**: 1 instance — Unnecessary mode argument in `open()`
- **UP017**: 1 instance — Use `datetime.UTC` alias
- **UP037**: 1 instance — Remove quotes from type annotation
- **UP041**: 1 instance — Replace aliased `asyncio.TimeoutError` with `TimeoutError`

### Type Errors (138 total across 50 files)
- Missing type annotations in function signatures
- Incompatible return types
- Missing imports for typing constructs
- Optional type mismatches

## Files with Issues

### Critical / Blocking
None — all files import successfully and pass syntax checks.

### High Priority (Fixable)
| File | Issues |
|------|--------|
| `shared/database/models.py` | 18 ruff errors (UP042, UP045, UP006) |
| `shared/kafka/producer.py` | 3 ruff errors (UP041, UP037) |
| `shared/llm/router.py` | 2 ruff errors (UP042) |
| `shared/models/job.py` | 12 ruff errors (UP042, I001, F401) |
| `shared/models/company.py` | 4 ruff errors (UP042, F401) |
| `shared/models/user.py` | 4 ruff errors (UP042) |
| `shared/utils/recommender.py` | 6 ruff errors (F841, B905, F541) |
| `shared/utils/url.py` | 1 ruff error (F821) |
| `shared/utils/resume_parser.py` | 2 ruff errors (SIM102, E741) |
| `shared/utils/logging.py` | 2 ruff errors (UP017, SIM105) |
| `shared/utils/health.py` | 1 ruff error (B905) |
| `tests/integration/test_api.py` | 1 ruff error (I001) |
| `tests/unit/test_pipeline.py` | 5 ruff errors (I001, F401) |
| `tests/unit/test_scam_detector.py` | 2 ruff errors (I001, F401) |
| `tests/unit/test_cleaner.py` | 1 ruff error (I001) |
| `tests/unit/test_salary_extractor.py` | 1 ruff error (I001) |

### Medium Priority (Type Errors)
| File | Mypy Errors |
|------|-------------|
| `services/gateway/main.py` | Multiple type mismatches |
| `services/collector/main.py` | Multiple type mismatches |
| `services/cleaner/main.py` | Multiple type mismatches |
| `services/deduplicator/main.py` | Multiple type mismatches |
| `services/verifier/main.py` | Multiple type mismatches |
| `services/enrichment/main.py` | Multiple type mismatches |
| `services/embedder/main.py` | Multiple type mismatches |
| `services/search/main.py` | Multiple type mismatches |
| `services/analytics/main.py` | Multiple type mismatches |
| `services/feedback/main.py` | Multiple type mismatches |
| `services/notifier/main.py` | Multiple type mismatches |
| `services/orchestrator/main.py` | Multiple type mismatches |
| `shared/database/session.py` | Multiple type mismatches |
| `shared/database/base.py` | Multiple type mismatches |
| `shared/kafka/consumer.py` | Multiple type mismatches |
| `shared/redis/client.py` | Multiple type mismatches |

### Low Priority / Style Only
All UP* (pyupgrade) rules are style modernization suggestions that don't affect runtime behavior.

## Recommendations

1. **Auto-fix**: Run `ruff check --fix` to resolve 251 fixable lint errors
2. **Manual fix**: Address remaining ruff errors (175) and mypy errors (138)
3. **Structural**: Some mypy errors may require adding type stubs for external dependencies
4. **Testing**: All 88 files import successfully; runtime smoke tests pass

## Next Steps

Per user decision: **Report only** — no code changes applied. Fixes should be applied in a separate pass after reviewing this report.
