# Production Readiness Checklist — AI Agent Primary Grader

All five criteria below must be met before the Python shadow run is removed
from `run_batch.py`. No single criterion can be waived independently.

---

## Criteria

### 1. Benchmark Accuracy ≥ 90% Exact-Match

- Run `python benchmark_agent.py` against the current `benchmark_truth.csv`.
- The exact-match rate (AI grade == Manual grade) printed in the accuracy
  report must be **≥ 90%**.
- Record the run date and result in the sign-off table below.

| Date | Exact Match % | Within-1 % | False Rejects | False Passes | Pass? |
|------|--------------|------------|---------------|--------------|-------|
|      |              |            |               |              |       |

---

### 2. Zero False Rejections on the Last 50 Submissions

- A false rejection is any submission where the manual grade is ≥ 3 but the
  AI assigned 1 or 2, causing an escalation email to the instructor instead
  of feedback to the student.
- Pull the most recent 50 rows from `ADF_Homework_Autograder_Rejects_test`
  and cross-reference against known manual grades.
- **Zero false rejections** is a hard gate — a single confirmed false
  rejection blocks promotion.

| Batch Date | Submissions Reviewed | False Rejections Found | Pass? |
|------------|---------------------|----------------------|-------|
|            |                     |                      |       |

---

### 3. Shadow Log Agreement Rate ≥ 85% Over 3 Consecutive Batch Runs

- Run `python analyze_shadow_log.py <log>` after each of 3 consecutive
  batch runs.
- The agreement rate (`|delta| ≤ 1`) must be **≥ 85% in all three runs**.
- A single run below 85% resets the counter — three passing runs must be
  consecutive.

| Run # | Log File | Agreement Rate | Pass? |
|-------|----------|---------------|-------|
| 1     |          |               |       |
| 2     |          |               |       |
| 3     |          |               |       |

---

### 4. All Confidence Scores Logged for Analysis

- Every row written to `ADF_Homework_test` or `ADF_Homework_Autograder_Rejects_test`
  must include a `confidence` value (0.0–1.0) from `finalize_grade`.
- Verify by querying both test tables: `SELECT COUNT(*) WHERE confidence IS NULL`
  must return 0.
- Additionally, review the confidence distribution: if more than 20% of
  submissions score ≤ 0.5, flag for review before proceeding.

| Table | NULL confidence rows | ≤ 0.5 confidence % | Pass? |
|-------|---------------------|-------------------|-------|
| ADF_Homework_test | | | |
| ADF_Homework_Autograder_Rejects_test | | | |

---

### 5. Ali (Project Director) Sign-Off

- Ali reviews `benchmark_results.csv` and the three shadow log reports
  personally before promotion.
- Sign-off confirms: the grading quality, false-rejection rate, and
  confidence distribution are acceptable for student-facing use.

| Sign-off Date | Reviewer | Notes |
|--------------|----------|-------|
|              | Ali      |       |

---

## All Criteria Met?

Check all boxes before removing the shadow:

- [ ] Criterion 1 — Benchmark accuracy ≥ 90%
- [ ] Criterion 2 — Zero false rejections on last 50 submissions
- [ ] Criterion 3 — Shadow agreement ≥ 85% over 3 consecutive runs
- [ ] Criterion 4 — Confidence scores fully logged, distribution reviewed
- [ ] Criterion 5 — Ali sign-off received

**Do not remove the shadow run until every box is checked.**

---

## Rollback Plan

If any grading issue is discovered after Sprint 4 ships, revert to the
Python hybrid grader as primary by making the following change in
`run_batch.py`.

### What to change

In `run_batch.py`, the agent is currently called as the primary grader and
the hybrid grader runs as a shadow (comparison only, no writes):

```python
# Current: Agent is primary
result = autograde_homework_agent(hw)          # primary — drives all writes

try:
    hybrid_result = autograde_homework_hybrid(hw)
    hybrid_grade  = int(hybrid_result.get("grade", 1))
    delta         = hybrid_grade - grade
    print(f"🔬  Shadow: Agent={grade} | Hybrid={hybrid_grade} | Delta={delta:+d}")
except Exception:
    pass
```

To roll back, swap which grader is primary and which is shadow:

```python
# Rollback: Hybrid (Python) is primary
result = autograde_homework_hybrid(hw)         # primary — drives all writes

try:
    agent_result = autograde_homework_agent(hw)
    agent_grade  = int(agent_result.get("grade", 1))
    grade        = int(result.get("grade", 1))
    delta        = agent_grade - grade
    print(f"🔬  Shadow: Hybrid={grade} | Agent={agent_grade} | Delta={delta:+d}")
except Exception:
    pass
```

No other files need to change. The routing logic (grade ≤ 2 → rejects,
grade ≥ 3 → main table) reads from `result` and is unaffected by which
grader produces it.

### Rollback checklist

1. Edit `run_batch.py` as shown above.
2. Run one manual batch against a known submission to confirm Python grades
   are being written to the test tables.
3. Verify escalation emails route correctly for a grade ≤ 2 submission.
4. Notify Ali that rollback is active and log the incident date below.

| Rollback Date | Triggered By | Reason | Resolved Date |
|--------------|-------------|--------|--------------|
|              |             |        |              |
