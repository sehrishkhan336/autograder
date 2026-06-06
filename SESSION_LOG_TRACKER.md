# Session Log Tracker

## Current Status

Phase: Sprint 4 — Benchmark Calibration
Session Date: June 5 2025
Current Focus: AI prompt calibration — reduce false rejects on high-scoring submissions

---

## Calibration Baseline (END OF SESSION — June 5 2025)

Source: benchmark_input.csv (15 rows from TestingManualGrading.xlsx — Bala's grades)

| Metric | AI Agent | Python Grader |
|--------|----------|---------------|
| Exact match | 6/15 (40.0%) | 7/15 (46.7%) |
| Within-±1 | 10/15 (66.7%) | 10/15 (66.7%) |
| False passes | 1 | 3 |
| False rejects | 3 | 2 |

EXIT CRITERION: AI within-±1 ≥ 90% = need 14/15
CURRENT GAP: 4 more rows must move within-±1

This is the OFFICIAL baseline. Every future improvement must beat these numbers.

---

## Today's Commits (June 5 2025)

| Commit | File(s) | What Changed |
|--------|---------|--------------|
| 94a63ab | file_tools.py | _is_real_file() Mac artifact filter added |
| a4aaf5c | benchmark_input.csv, build_benchmark_input.py, TestingManualGrading.xlsx | Excel as benchmark source — replaces benchmark_truth.csv |
| 738a16e | autograde_agent.py | AI_TEMPERATURE=0.2 wired from .env to API call |
| 62340e6 | benchmark_three_way.py | Benchmark reads from CSV — DB dependency removed |
| d0821fe | autograde_agent.py, autograde_tools.py | Multi-file SQL policy: grade content not format |

---

## Current State of Each Benchmark Row

| HWID | Student | Manual | AI | Python | AI Status | PY Status | Root Cause Remaining |
|------|---------|--------|-----|--------|-----------|-----------|----------------------|
| 376954 | Ahmad Taha | 5 | 1 | 5 | AI-FR | EXACT | AI prompt: awards grade 1 on complete submission |
| 376955 | Carla Hope | 1 | 5 | 5 | AI-FP | PY-FP | No scope gate: 1/9 tasks = full credit |
| 376956 | Odee Egbuho | 4 | 4 | 4 | EXACT | EXACT | ✅ Done |
| 376957 | Tinotenda M. | 5 | 1 | 5 | AI-FR | EXACT | AI prompt: awards grade 1 on complete submission |
| 376958 | Koffi Kouame | 4 | 3 | 5 | WITHIN-1 | WITHIN-1 | ✅ Acceptable |
| 376959 | Patricia A-T | 4 | 1 | 1 | AI-FR | PY-FR | ZIP content inspection needed — policy fix had no effect |
| 376960 | Reginald W. | 1 | 1 | 1 | EXACT | EXACT | ✅ Done |
| 376961 | Reginald W. | 1 | 1 | 1 | EXACT | EXACT | ✅ Done |
| 376962 | Aster Tadesse | 5 | 4 | 4 | WITHIN-1 | WITHIN-1 | ✅ Acceptable |
| 376963 | Megan D-M | 4 | 5 | 4 | WITHIN-1 | EXACT | ✅ Acceptable |
| 376964 | Aster Tadesse | 1 | 1 | 3 | EXACT | PY-FP | Python threshold too lenient |
| 376965 | Patricia A-T | 3 | 5 | 3 | WITHIN-1 | EXACT | ✅ Acceptable |
| 376966 | Saba G | 1 | 1 | 3 | EXACT | PY-FP | Python reads blank template as content |
| 376967 | Solome F. | 5 | 5 | 3 | EXACT | WITHIN-1 | ✅ Acceptable |
| 376968 | Samerah B. | 3 | 4 | 2 | WITHIN-1 | WITHIN-1 | ✅ Acceptable |

---

## Remaining Failures — Root Causes and Fix Targets

### AI False Rejects (grade 1 on manual 4-5) — HIGHEST PRIORITY
These 3 rows are blocking the exit criterion most severely:

| HWID | Manual | AI | Root Cause | Fix |
|------|--------|-----|------------|-----|
| 376954 | 5 | 1 | AI prompt gives grade 1 on substantively complete Auditing & EH submission | AI SYSTEM_PROMPT calibration |
| 376957 | 5 | 1 | AI prompt gives grade 1 on complete Data Profiling submission | AI SYSTEM_PROMPT calibration |
| 376959 | 4 | 1 | ZIP content inspection needed — extracted SQL may be empty or rubric mismatch | Inspect ZIP first |

### AI False Pass (grade 5 on manual 1) — CRITICAL
| HWID | Manual | AI | Root Cause | Fix |
|------|--------|-----|------------|-----|
| 376955 | 1 | 5 | No scope coverage check — 1/9 tasks done but AI awards 5 | Scope gate in SYSTEM_PROMPT |

### Python False Passes — MEDIUM PRIORITY
| HWID | Manual | PY | Root Cause | Fix |
|------|--------|-----|------------|-----|
| 376955 | 1 | 5 | No scope coverage check | Scope gate in autograde_tools.py |
| 376964 | 1 | 3 | Python too lenient on severely incomplete submissions | Threshold calibration |
| 376966 | 1 | 3 | Blank DOCX template reads as content | Empty-content gate |

---

## Current Blockers

1. HWID 376954 and 376957: AI gives grade 1 on manual-5 submissions. Highest impact fix. Temperature at 0.2 did not stabilize these — prompt calibration needed.
2. HWID 376959: Multi-file policy fix committed but had zero effect. ZIP must be inspected directly to find true root cause. Set aside until ZIP inspection done.
3. HWID 376955: AI and Python both false pass. Scope gate needed.
4. Python false passes (376964, 376966): threshold and empty-content gate needed.
5. Ali confirmation needed: multi-file policy change (commit d0821fe) before production.
6. Confidence score persistence not implemented.
7. Agent vs Hybrid delta alerting not implemented.

---

## Next Session — Start Here (IN ORDER)

### STEP 1 — Inspect HWID 376959 ZIP directly (15 min)
Understand why grade=1 persists after multi-file fix.
Command:
  python -c "
  import zipfile
  with zipfile.ZipFile('path/to/hw_1014_19466_WORKING_WITH_VARIABLES_LAB_1.zip') as z:
      print('Files:', z.namelist())
      for name in z.namelist():
          print(f'--- {name} ---')
          print(z.read(name).decode(errors='ignore')[:500])
  "
Download ZIP from HomeworkLink in benchmark_input.csv first.
Report findings before any fix.

### STEP 2 — AI prompt calibration for false rejects (376954, 376957)
Both are manual-5 submissions getting AI grade 1.
Python grades them correctly as 5.
Root cause: AI prompt is too conservative — defaults to grade 1 on certain submission types.
Fix: Add explicit guidance to SYSTEM_PROMPT — do not award grade 1 unless submission
is empty, completely wrong section, or has zero extractable content.
Show diff. Get approval. Run benchmark. Compare before/after.

### STEP 3 — Scope gate for 376955
Student completed 1/9 required tasks. AI gives 5, Python gives 5. Manual is 1.
Add to SYSTEM_PROMPT: if student answered fewer than 50% of required questions → max grade 2.
Coordinate with Python validator for same gate.

### STEP 4 — Python false pass fixes (376964, 376966)
Empty-content gate and threshold calibration.

### STEP 5 — Benchmark rerun after each individual fix
Never stack multiple fixes before benchmarking.
Always compare before/after. Never claim improvement without evidence.

---

## Safety Rules (always active)

- Benchmark command: set PYTHONIOENCODING=utf-8 && python benchmark_three_way.py
- All writes to test tables only. No production writes until Ali signs off.
- AI_TEMPERATURE=0.2 (confirmed wired as of commit 738a16e)
- Score-to-grade thresholds: 0.75/0.65/0.50/0.20 (Ali approved, do not change)
- benchmark_truth.csv = DEPRECATED. Source of truth = benchmark_input.csv
- Multi-file policy change (d0821fe) needs Ali confirmation before production
- Show diff before every save. Commit one change at a time.
