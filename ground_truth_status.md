# Ground Truth Status
_Generated: 2026-05-19 (Tuesday) — scheduled task run_

---

## ⚠️ benchmark_truth.csv — FILE DOES NOT EXIST

`benchmark_truth.csv` has **not been created yet**. This file is a Sprint 4 deliverable
(Phase 2 of the recalibration plan: expand benchmark ground truth from 15 to ~50 entries).

The expected schema (from `benchmark_agent.py` and `benchmark_three_way.py`):

```
HomeworkID, ManualGrade, Notes
```

> **Note:** The scheduled task spec references an `expected_concepts` field. This column does
> **not** appear in the current code schema. Confirm with Ali whether `expected_concepts` should
> be added before the file is created.

---

## De-facto Ground Truth — benchmark_three_way_results.csv

Until `benchmark_truth.csv` is created, the `ManualGrade` column in
`benchmark_three_way_results.csv` (archived 2026-05-11) is the only on-disk ground truth.

**Total entries: 15** (baseline run — 2026-05-11)

### Grade Distribution (ManualGrade)

| Expected Grade | Count | % of total |
|:--------------:|------:|----------:|
| 1              | 3     | 20.0%     |
| 2              | 2     | 13.3%     |
| 3              | 2     | 13.3%     |
| 4              | 4     | 26.7%     |
| 5              | 4     | 26.7%     |
| **Total**      | **15**| **100%**  |

Grade coverage is broadly distributed across all 5 grade levels. Low-grade entries (1–2) are
slightly under-represented relative to the sprint target; the expanded set should aim for
roughly 10 entries per grade level.

### Assignment Type Distribution (SectionName)

| Section / Assignment Type                       | Count |
|-------------------------------------------------|------:|
| System Functions                                | 3     |
| Data Profiling                                  | 2     |
| Auditing & Error Handling                       | 1     |
| Parameters                                      | 1     |
| Query Editor Features                           | 1     |
| Variables                                       | 1     |
| Joins                                           | 1     |
| Temp Data Structures                            | 1     |
| Data Connectivity                               | 1     |
| IPBC – DBA Roles                                | 1     |
| Mobile App                                      | 1     |
| IPBC - Mortgage Project R2:SP5: Story 7         | 1     |
| **Total unique types**                          | **12** |

System Functions is the only repeated section (3 entries). All others appear once.
The expanded benchmark should increase coverage depth across the most-common assignment types.

---

## Missing / Incomplete Rows

**None.** All 15 rows in the de-facto ground truth have `HomeworkID` and `ManualGrade`
populated. No `Notes` column is present in the current three-way results file; this is
expected — notes are optional.

---

## New Entries Since Last Run

**This is the first run of this report.** No prior `ground_truth_status.md` existed.
Subsequent runs will diff against this baseline to flag newly added rows.

---

## Gap to 50-Entry Target

| Metric                  | Current | Target | Gap         |
|-------------------------|--------:|-------:|------------:|
| Total ground-truth rows | 15      | ~50    | **−35**     |
| Grade levels covered    | 5/5     | 5/5    | 0           |
| Unique assignment types | 12      | TBD    | —           |

**35 additional manually-graded entries are needed** before the Sprint 4 Phase 2 milestone
is complete and a recalibrated benchmark can be run. At the current pace (0 new entries since
2026-05-11), this work has not started.

---

## Action Items

1. **Create `benchmark_truth.csv`** with columns `HomeworkID, ManualGrade, Notes` and seed it
   from the 15 existing `ManualGrade` values in `benchmark_three_way_results.csv`.
2. **Clarify `expected_concepts` column** with Ali — add if required, otherwise close the gap
   in the scheduled task spec.
3. **Add 35 manually-graded entries** to reach the ~50-row target before recalibration runs.
4. Prioritize grade levels 1 and 2 (currently 5 entries combined) and diversify section types.

---

_Next scheduled run: Friday 2026-05-22 at 09:00 AM_
