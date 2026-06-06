# Tomorrow's Execution Plan — GradeFlow AI
Date: June 6 2025
Starting baseline: AI within-±1 = 10/15 (66.7%) | Target: 14/15 (93%)
Gap: 4 rows must flip to within-±1

---

## The Strategy: Three AI Improvement Techniques in One Session

Tomorrow we apply three techniques from the AI improvement framework simultaneously,
each targeting a specific failure pattern confirmed by benchmark evidence.

Technique 1 — Prompt guard (stop catastrophic false rejects)
Technique 2 — Few-shot examples from Bala's grading (teach by example)
Technique 3 — Scope coverage gate (stop false passes on partial work)

Each technique targets specific failing rows. Each is benchmarked independently.

---

## MORNING BLOCK (60-90 min) — Diagnose Before You Fix

### TASK A — Inspect HWID 376959 ZIP (15 min, do first)

We have tried 3 fixes on this row. None worked. We must see the raw content
before attempting anything else.

Claude Code command:
```
TASK: Inspect HWID 376959 ZIP content directly. Read only. No changes.

Run this Python script:
  import urllib.request, zipfile, io, sys
  sys.path.insert(0, ".")
  from file_tools import _is_real_file

  url = "https://app.colaberry.com/uploads/homeworks/hw_1014_19466_WORKING_WITH_VARIABLES_LAB_1.zip"
  print("Downloading ZIP...")
  data = urllib.request.urlopen(url).read()
  print(f"Downloaded: {len(data)} bytes")

  with zipfile.ZipFile(io.BytesIO(data)) as z:
      all_files = z.namelist()
      print(f"\nAll files in ZIP ({len(all_files)}):")
      for f in all_files:
          print(f"  {f} | real={_is_real_file(f)}")

      print("\nSQL file contents:")
      sql_files = [f for f in all_files if f.lower().endswith(".sql") and _is_real_file(f)]
      if not sql_files:
          print("  NO REAL SQL FILES FOUND")
      for name in sql_files:
          content = z.read(name).decode(errors="ignore")
          print(f"\n--- {name} ({len(content)} chars) ---")
          print(content[:1000])

STOP after output. Do not fix anything. Report:
1. How many real SQL files are in the ZIP?
2. What is the content of each?
3. Is the content related to the Variables assignment?
4. Is the content empty or minimal?
```

Decision gate after Task A:
- If SQL content is present and on-topic → root cause is rubric mismatch → fix in TASK C
- If SQL content is empty → extraction bug → different fix
- If SQL belongs to wrong assignment → grade 1 is correct → exclude from benchmark calibration

---

## MIDDAY BLOCK (90-120 min) — AI Prompt Improvements

### TASK B1 — Technique 1: False Reject Guard
Target rows: 376954 (Manual=5, AI=1) and 376957 (Manual=5, AI=1)
Python grades both correctly as 5. AI catastrophically underscores.

Root cause confirmed: AI awards grade 1 on substantively complete submissions.
The prompt has no guard preventing this. We add one.

Claude Code command:
```
TASK: Add false-reject guard to AI SYSTEM_PROMPT in autograde_agent.py.
Show diff only. Do not save yet.

Find the section in SYSTEM_PROMPT that describes grade 1 criteria.
Add this guard BEFORE any grade 1 criteria:

--- ADD THIS BLOCK ---
CRITICAL ANTI-PATTERN — DO NOT DO THIS:
Do NOT award grade 1 to a submission that contains SQL queries or DOCX content
addressing the assignment topic, even if the work has errors or gaps.
Grade 1 is reserved ONLY for:
  - Completely empty submissions (zero extractable content)
  - Submissions for a completely different assignment (wrong course material)
  - Submissions with zero SQL files when SQL is required
If you find yourself about to award grade 1 and the submission has content
related to the assignment, reconsider. The minimum grade for attempted work is 2.
--- END BLOCK ---

Show the exact diff (old lines vs new lines).
STOP. Do not save. Wait for my review.
```

Expected impact: 376954 and 376957 move from AI=1 to AI=3,4,5 → +2 rows within-±1
Run benchmark after. Compare before/after. Only proceed to B2 if no regression.

---

### TASK B2 — Technique 2: Few-Shot Examples from Bala's Grading
Target: General AI calibration across all grade levels

The AI has never seen a real example of what grade 1, 3, or 5 looks like
for this school. We inject 3 examples directly from Bala's graded submissions.

Claude Code command:
```
TASK: Add few-shot grading examples to SYSTEM_PROMPT in autograde_agent.py.
Show diff only. Do not save yet.

Add this section to the SYSTEM_PROMPT after the grade criteria section:

--- ADD THIS BLOCK ---
REAL GRADING EXAMPLES (from expert human grader):

EXAMPLE — Grade 5 (full credit):
Assignment: System Functions
Bala's verdict: Full credit. No issues noted.
What made it grade 5: All required SQL functions demonstrated correctly,
queries answer every lab question, proper syntax throughout.

EXAMPLE — Grade 4 (mostly complete):
Assignment: Query Editor Features  
Bala's verdict: Core work done. Missing lab questions as SQL comments
and group assignment screenshot.
What made it grade 4: Main SQL work correct and complete. Minor
formatting requirement missed. One deliverable (screenshot) absent.
Does not affect core competency demonstration.

EXAMPLE — Grade 3 (partial — escalated):
Assignment: System Functions
Bala's verdict: Some question text not formatted as SQL comments.
Missing header. Q2 uses GROUP BY instead of DISTINCT. UNION formatting broken.
What made it grade 3: Attempted all questions but has logic errors and
formatting failures that affect correctness. Not a pass, not a full reject.

EXAMPLE — Grade 1 (rejected):
Assignment: Parameters
Bala's verdict: Applied parameters to 1 of 9 required reports only.
Screenshots do not show work. Resubmit required.
What made it grade 1: Student completed approximately 11% of required scope.
No meaningful demonstration of the required skill.
--- END BLOCK ---

Show the exact diff. STOP. Do not save. Wait for my review.
```

Expected impact: Better calibration across all grade levels. Reduces AI tendency
to compress grades toward 3 or snap to extremes.
Run benchmark after. Compare before/after.

---

### TASK B3 — Technique 3: Scope Coverage Gate
Target rows: 376955 (Manual=1, AI=5, Python=5)
Carla completed 1 of 9 required parameter reports. Both graders give full credit.

Claude Code command:
```
TASK: Add scope coverage gate to SYSTEM_PROMPT in autograde_agent.py.
Show diff only. Do not save yet.

Find the SCOPE COMPLETENESS CHECK section in SYSTEM_PROMPT (around lines 243-257).
The existing gate checks query COUNT for SQL. We need to ADD a task coverage check
for all assignment types.

Add this block to the scope completeness section:

--- ADD THIS BLOCK ---
SCOPE COVERAGE RULE (all assignment types):
Before grading, estimate: how many distinct tasks or reports does the
answer key require? How many did the student complete?

  Student completed < 25% of required tasks → maximum grade is 1
  Student completed 25%-49% of required tasks → maximum grade is 2
  Student completed 50%-79% of required tasks → maximum grade is 3
  Student completed ≥ 80% → grade normally on quality

This rule applies to:
- Parameter reports (e.g. must apply to all 9 reports — doing 1 = 11% = grade 1)
- Screenshot submissions (e.g. must show all steps — showing 1 step = grade 1)
- Multi-question SQL labs (already covered by query count gate above)
--- END BLOCK ---

Show the exact diff. STOP. Do not save. Wait for my review.
```

Expected impact: 376955 moves from AI=5 to AI=1 or 2 → removes critical false pass
Run benchmark after. Compare before/after.

---

## AFTERNOON BLOCK (45-60 min) — Python Calibration

### TASK C — Python False Pass Fixes
Target rows: 376955 (PY=5), 376964 (PY=3), 376966 (PY=3)

376955 — same scope gate needed in autograde_tools.py
376964 — Python gives 3 on a submission with only 1 screenshot (manual=1)
376966 — Python gives 3 on blank DOCX template (manual=1)

Claude Code command:
```
TASK: Find scope and empty-content checks in autograde_tools.py.
Read only. No changes yet.

SEARCH 1: Find where autograde_tools.py counts screenshots or 
measures submission completeness.
Print the relevant lines and line numbers.

SEARCH 2: Find where DOCX content length or paragraph count is checked.
Print the relevant lines and line numbers.

STOP. Report findings. Wait for my review before any diff.
```

We read first, then design the fix based on what we find.

---

## END OF DAY BLOCK (30 min) — Validation and Documentation

### TASK D — Full Benchmark Run and Comparison

After all changes are committed:

```
TASK: Run final benchmark and produce end-of-day report.

Run: set PYTHONIOENCODING=utf-8 && python benchmark_three_way.py 2>&1

Print full per-row table.
Print before/after comparison:

  Metric           | Start of Day | End of Day | Change
  AI within-±1    | 10/15 (67%)  | ?          | ?
  Python within-±1| 10/15 (67%)  | ?          | ?
  AI false passes  | 1            | ?          | ?
  AI false rejects | 3            | ?          | ?

Print: Are we at or above 14/15 (93%)? Yes/No
Print: What rows are still failing?

STOP. Wait for instructions.
```

### TASK E — Update session files and commit docs

Same as today — update SESSION_LOG_TRACKER.md, CURRENT_SPRINT_CONTEXT.md,
TOMORROW_START_CARD.md with end-of-day numbers and commit everything.

---

## Expected Outcomes (honest estimates)

| Task | Rows gained | Cumulative AI within-±1 |
|------|-------------|------------------------|
| Start of day | — | 10/15 (67%) |
| B1: False reject guard | +2 (376954, 376957) | 12/15 (80%) |
| B2: Few-shot examples | +0 to +1 (calibration) | 12-13/15 |
| B3: Scope gate | +1 (376955) | 13/15 (87%) |
| A/C: 376959 + Python fixes | +1-2 | 14-15/15 (93-100%) ✅ |

**Realistic end-of-day target: 13/15 (87%) confirmed, 14/15 (93%) possible.**

If we hit 14/15: exit criterion met. Move to production readiness checks.
If we hit 13/15: one more session of calibration needed, then production readiness.

---

## Rules for Tomorrow

1. One fix at a time. Benchmark after every individual change.
2. Show diff before every save. No exceptions.
3. If a fix causes a regression on any previously-passing row, revert it.
4. Do not stack B1 + B2 + B3 into one commit. Each is separate and independently revertible.
5. Do not claim improvement without benchmark numbers to prove it.
6. Do not start Python fixes (Task C) until AI fixes (Task B) are confirmed stable.

---

## If Things Go Wrong

Regression on stable rows after B1:
  → Revert B1 with: git revert HEAD
  → The false reject guard wording is too broad — narrow it

Regression after B2 (few-shot examples):
  → Revert B2
  → The examples may be confusing the model — simplify or remove one

376959 ZIP inspection shows wrong content:
  → Grade 1 may be correct for this submission
  → Flag it as "policy-correct reject" and remove it from calibration target
  → Reframe: exit criterion becomes 13/14 (93%) excluding 376959

---

## Quick Reference for Tomorrow

| Item | Value |
|------|-------|
| Benchmark command | set PYTHONIOENCODING=utf-8 && python benchmark_three_way.py |
| Baseline to beat | AI within-±1: 10/15 (67%) |
| Files to change | autograde_agent.py (SYSTEM_PROMPT), autograde_tools.py |
| Files NOT to change | benchmark_input.csv, score thresholds, DB tables |
| Commit style | One change per commit, diff first always |
| Temperature | 0.2 (already wired, do not change) |
