# Basecamp Update — GradeFlow AI Sprint 4
Date: June 5 2025
To: Ali
From: Sehrish

---

## What We Completed Today

Sprint 4 calibration session completed. Five commits shipped:

**Architecture improvements (no grading logic changed):**
- Benchmark now reads from a frozen Excel file (Bala's manual grades) instead of the live database. This makes every benchmark run reproducible and removes the risk of input data changing mid-calibration.
- AI grading temperature corrected from default (1.0) to approved value (0.2). This reduces grade variance between runs on identical submissions.

**Policy fix (needs your confirmation before production):**
- Multi-file SQL submissions now have their content graded instead of being automatically rejected. This aligns with Bala's grading approach. We need your sign-off before this goes to production.

---

## Benchmark Results

Current accuracy against Bala's 15 manual grades:

| Metric | AI Agent | Python Grader |
|--------|----------|---------------|
| Within-±1 of manual grade | 10/15 (67%) | 10/15 (67%) |
| Exact match | 6/15 (40%) | 7/15 (47%) |
| False passes (wrong accept) | 1 | 3 |
| False rejects (wrong escalation) | 3 | 2 |

Target: ≥90% within-±1. Gap: 4 more rows needed.

---

## What Still Needs Work

Three patterns are causing the remaining gap:

1. **AI false rejects on strong submissions** — Two complete, high-quality submissions (manual grade 5) are being graded as 1 by the AI. Python grades them correctly as 5. This is a prompt calibration issue we will address next session.

2. **Scope coverage not checked** — One submission where the student completed 1 of 9 required tasks is being graded as a pass by both graders. A scope gate is needed.

3. **One submission still under investigation (HWID 376959)** — Patricia's Variables lab continues to grade as 1 despite multiple fix attempts. We need to inspect the ZIP file contents directly to find the true cause.

---

## Decision Needed From You

The multi-file SQL policy change is committed to the test branch but **not yet in production**. Before we deploy:

> Should the system grade the content of multi-file SQL submissions, or continue rejecting them and escalating to the grading team?

Bala's grading of HWID 376959 accepted a two-file submission based on content quality. We have aligned the system to match that approach, but want your explicit approval before it goes live.

---

## Current Status: 🟡 Yellow

Calibration is progressing. No regressions introduced today. Architecture is now clean and reproducible. Remaining gap (4 rows) is understood and has a clear fix plan. Production deployment is not recommended until the 90% target is reached.

Next session: AI prompt calibration for false rejects. Expected to recover 2 of the 4 remaining rows.

---
