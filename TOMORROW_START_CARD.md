# Tomorrow Start Card — GradeFlow AI
Session date: June 5 2025 (end of session)
Next session starts here. Read this first, then say "session startup."

---

## Where We Left Off

Benchmark baseline locked at: AI within-±1 = 10/15 (66.7%)
Target: 14/15 (93%) ← need 4 more rows

All infrastructure is clean:
- benchmark_input.csv = frozen input from Bala's Excel (15 rows, all links present)
- benchmark_three_way.py = reads CSV only, no DB calls
- Temperature = 0.2 (confirmed stable, 13/15 rows identical across runs)
- Run command: set PYTHONIOENCODING=utf-8 && python benchmark_three_way.py

---

## The 4 Rows We Need to Fix

| # | HWID | Manual | AI Now | PY Now | Fix | Expected gain |
|---|------|--------|--------|--------|-----|---------------|
| 1 | 376954 | 5 | 1 | 5 | AI prompt calibration | +1 AI row |
| 2 | 376957 | 5 | 1 | 5 | AI prompt calibration | +1 AI row |
| 3 | 376955 | 1 | 5 | 5 | Scope gate (AI + PY) | +1 AI +1 PY row |
| 4 | 376959 | 4 | 1 | 1 | ZIP inspection first | Unknown |

Fix rows 1+2+3 = reach 13/15 (87%) — one row short.
Fix row 4 as well = reach 14-15/15 (93-100%) — exit criterion met.

---

## Tomorrow's Task Order

### TASK A — Inspect HWID 376959 ZIP (do first, 15 min)
Find why grade=1 persists. Download the ZIP from benchmark_input.csv HomeworkLink.
HomeworkLink: https://app.colaberry.com/uploads/homeworks/hw_1014_19466_WORKING_WITH_VARIABLES_LAB_1.zip

Claude Code command:
  python -c "
  import urllib.request, zipfile, io
  url = 'https://app.colaberry.com/uploads/homeworks/hw_1014_19466_WORKING_WITH_VARIABLES_LAB_1.zip'
  data = urllib.request.urlopen(url).read()
  with zipfile.ZipFile(io.BytesIO(data)) as z:
      print('Files:', z.namelist())
      for name in z.namelist():
          from file_tools import _is_real_file
          if _is_real_file(name) and name.lower().endswith('.sql'):
              content = z.read(name).decode(errors='ignore')
              print(f'--- {name} ({len(content)} chars) ---')
              print(content[:800])
  "
Report: what files are in the ZIP, what SQL content is extracted.

### TASK B — AI prompt calibration for 376954 and 376957
Both are manual-5 submissions. Python correctly gives 5. AI gives 1.
These are NOT empty submissions. AI is catastrophically undergrading.

Add to SYSTEM_PROMPT (show diff, get approval first):
  "IMPORTANT: Only award grade 1 if the submission is completely empty,
  contains no SQL code whatsoever, or belongs to an entirely different
  assignment. Do not award grade 1 to submissions that contain SQL queries
  addressing the assignment topic, even if those queries have issues."

Run benchmark after. Compare before/after. Report numbers.

### TASK C — Scope gate for 376955
Student did 1 of 9 required tasks. Both graders give 5. Manual is 1.
Add scope coverage check — if student answered <50% of required questions,
cap grade at 2 regardless of quality of answers provided.
Show diff. Get approval. Run benchmark. Compare before/after.

---

## Do Not Touch (until calibration complete)

- Confidence score persistence
- Agent vs Hybrid delta alerting
- Production deployment
- Email workflow
- Schema changes
- benchmark_input.csv (frozen — never modify)

---

## Ali Items Pending

1. Multi-file SQL policy (commit d0821fe) — needs Ali approval before production
2. Basecamp update drafted — review BASECAMP_DRAFT.md before posting

---

## Quick Reference

| Item | Value |
|------|-------|
| Repo | C:\colaberry\projects\autograder-phase1-test |
| Benchmark command | set PYTHONIOENCODING=utf-8 && python benchmark_three_way.py |
| Benchmark input | benchmark_input.csv (15 rows, Bala's grades) |
| Temperature | 0.2 (wired in autograde_agent.py commit 738a16e) |
| Score thresholds | 0.75/0.65/0.50/0.20 (Ali approved, do not change) |
| Last commit | d0821fe — multi-file SQL policy |
| Production status | NOT READY — 67% within-±1, need 90% |
