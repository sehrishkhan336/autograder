# Current Sprint Context

## Phase
Phase 2 — Sprint 4 Benchmark Calibration

## Current Objective
Achieve ≥90% within-±1 agreement between automated graders and Bala's manual grades.
Source of truth: benchmark_input.csv (generated from TestingManualGrading.xlsx)

## Benchmark Baseline (June 5 2025 — END OF SESSION)

Sample: 15 rows | Source: benchmark_input.csv

| Metric | AI Agent | Python Grader |
|--------|----------|---------------|
| Exact match | 6/15 (40.0%) | 7/15 (46.7%) |
| Within-±1 | 10/15 (66.7%) | 10/15 (66.7%) |
| False passes | 1 | 3 |
| False rejects | 3 | 2 |

EXIT CRITERION: AI within-±1 ≥ 90% = need 14/15
CURRENT GAP: 4 rows must flip to within-±1

## Rows Failing — Priority Order

| Priority | HWID | Manual | AI | Problem | Fix |
|----------|------|--------|-----|---------|-----|
| 🔴 1 | 376954 | 5 | 1 | AI false reject | AI prompt calibration |
| 🔴 1 | 376957 | 5 | 1 | AI false reject | AI prompt calibration |
| 🔴 2 | 376955 | 1 | 5 | AI+PY false pass | Scope gate |
| 🟡 3 | 376959 | 4 | 1 | Both false reject | ZIP inspection first |
| 🟡 4 | 376966 | 1 | PY=3 | PY false pass | Empty-content gate |
| 🟡 4 | 376964 | 1 | PY=3 | PY false pass | Threshold calibration |

## Completed This Session (June 5 2025)

| Commit | Change | Impact |
|--------|--------|--------|
| 94a63ab | _is_real_file() Mac artifact filter | Zero impact on 376959 |
| a4aaf5c | benchmark_input.csv from Excel | Architecture: DB-free benchmark |
| 738a16e | Temperature wired to 0.2 | Reduced variance from 5→2 unstable rows |
| 62340e6 | Benchmark reads from CSV not DB | Architecture: reproducible runs |
| d0821fe | Multi-file SQL: grade not reject | Zero impact on 376959 — ZIP inspection needed |

## Active Decisions Needing Ali Confirmation

1. Multi-file SQL policy change (commit d0821fe) — do not deploy to production without Ali approval
2. Grade thresholds: 0.75/0.65/0.50/0.20 — Ali approved, do not change

## Next Recommended Task
STEP 1: Inspect HWID 376959 ZIP content directly (download and extract)
STEP 2: AI prompt calibration for 376954 and 376957 (false rejects on manual-5 submissions)
STEP 3: Scope gate for 376955 (1/9 tasks = grade 5 is wrong)

## Scope Lock
Do not work on confidence score persistence, delta alerting, Power BI, email workflow,
schema changes, or production deployment until AI within-±1 reaches ≥90%.
