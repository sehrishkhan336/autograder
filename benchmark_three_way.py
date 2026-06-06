"""
benchmark_three_way.py — Four-way accuracy comparison runner.

Reads benchmark_truth.csv (columns: HomeworkID, ManualGrade, Notes),
fetches each homework from vw_Homework (read-only), runs both the AI
agent and the Python structural grader, and reports side-by-side
accuracy statistics.

No DB writes. No emails sent.

Output: benchmark_three_way_results.csv
"""

import csv
import logging
import os
from datetime import date

from autograde_agent import autograde_homework_agent
from autograde_tools import autograde_homework

# ----------------------------------------------------------------
# Logging — suppress INFO noise; silence httpx
# ----------------------------------------------------------------
logging.basicConfig(level=logging.WARNING, format="%(levelname)s | %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

TRUTH_CSV   = "benchmark_input.csv"
RESULTS_CSV = "benchmark_three_way_results.csv"


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------

def load_truth(path: str) -> list[dict]:
    """Read benchmark_input.csv → list of dicts with all fields needed for grading."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Benchmark input file not found: {path}")
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "HomeworkID":   int(row["HomeworkID"].strip()),
                "ManualGrade":  int(row["ManualGrade"].strip()),
                "StudentName":  row.get("StudentName", "Unknown").strip(),
                "SectionName":  row.get("SectionName", "").strip(),
                "HomeworkLink": row.get("HomeworkLink", "").strip(),
                "AnswerKey":    row.get("AnswerKey", "").strip(),
                "Notes":        row.get("Notes", "").strip(),
            })
    return rows



def _flags(manual: int, ai: int, py: int) -> str:
    """Generate flag string for a result row."""
    parts = []
    if manual <= 2 and ai >= 3:
        parts.append("AI-FP")
    if manual >= 3 and ai <= 2:
        parts.append("AI-FR")
    if manual <= 2 and py >= 3:
        parts.append("PY-FP")
    if manual >= 3 and py <= 2:
        parts.append("PY-FR")
    return " ".join(parts)


def write_results(path: str, rows: list[dict]) -> None:
    """Write per-submission results to CSV."""
    fieldnames = ["HWID", "Student", "Manual", "AI", "Python", "Flags"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_history_row(ai_exact: int, py_exact: int, ai_within: int,
                      py_within: int, ai_fr: int, ai_fp: int,
                      py_fr: int, py_fp: int, total: int) -> None:
    """Append a summary row to benchmark_history.csv for trend tracking."""
    history_path = "benchmark_history.csv"
    file_exists = os.path.exists(history_path)
    with open(history_path, "a", newline="", encoding="utf-8") as f:
        fieldnames = [
            "Date", "Total",
            "AI_Exact", "AI_Exact_Pct",
            "AI_Within1", "AI_Within1_Pct",
            "AI_FalseRejects", "AI_FalsePasses",
            "PY_Exact", "PY_Exact_Pct",
            "PY_Within1", "PY_Within1_Pct",
            "PY_FalseRejects", "PY_FalsePasses",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

        def pct(n, d):
            return f"{n / d * 100:.1f}%" if d > 0 else "—"

        writer.writerow({
            "Date": str(date.today()),
            "Total": total,
            "AI_Exact": ai_exact,
            "AI_Exact_Pct": pct(ai_exact, total),
            "AI_Within1": ai_within,
            "AI_Within1_Pct": pct(ai_within, total),
            "AI_FalseRejects": ai_fr,
            "AI_FalsePasses": ai_fp,
            "PY_Exact": py_exact,
            "PY_Exact_Pct": pct(py_exact, total),
            "PY_Within1": py_within,
            "PY_Within1_Pct": pct(py_within, total),
            "PY_FalseRejects": py_fr,
            "PY_FalsePasses": py_fp,
        })


# ----------------------------------------------------------------
# Main Runner
# ----------------------------------------------------------------

def main():
    truth_rows = load_truth(TRUTH_CSV)
    total = len(truth_rows)
    print(f"Loaded {total} entries from {TRUTH_CSV}\n")

    # Accuracy counters
    ai_exact = ai_within = ai_fr = ai_fp = 0
    py_exact = py_within = py_fr = py_fp = 0

    result_rows = []

    for entry in truth_rows:
        hwid         = entry["HomeworkID"]
        manual_grade = entry["ManualGrade"]

        print(f"Grading HWID {hwid} | ManualGrade={manual_grade}")

        hw = entry  # all fields already loaded from benchmark_input.csv
        student_name = hw.get("StudentName", "Unknown")

        # ── AI Agent ─────────────────────────────────────────────
        try:
            ai_result = autograde_homework_agent(hw)
            ai_grade  = int(ai_result.get("grade", 1))
        except Exception as e:
            logging.error(f"HWID {hwid}: AI agent error: {e}")
            ai_grade = None

        # ── Python Structural Grader ──────────────────────────────
        try:
            py_result = autograde_homework(hw)
            py_grade  = int(py_result.get("grade", 1))
        except Exception as e:
            logging.error(f"HWID {hwid}: Python grader error: {e}")
            py_grade = None

        # ── Metrics ───────────────────────────────────────────────
        if ai_grade is not None:
            if ai_grade == manual_grade:
                ai_exact += 1
            if abs(ai_grade - manual_grade) <= 1:
                ai_within += 1
            if manual_grade >= 3 and ai_grade <= 2:
                ai_fr += 1
            if manual_grade <= 2 and ai_grade >= 3:
                ai_fp += 1

        if py_grade is not None:
            if py_grade == manual_grade:
                py_exact += 1
            if abs(py_grade - manual_grade) <= 1:
                py_within += 1
            if manual_grade >= 3 and py_grade <= 2:
                py_fr += 1
            if manual_grade <= 2 and py_grade >= 3:
                py_fp += 1

        flags = _flags(
            manual_grade,
            ai_grade  if ai_grade  is not None else 0,
            py_grade  if py_grade  is not None else 0,
        )

        # ── Console output ────────────────────────────────────────
        ai_marker = ("✅" if ai_grade == manual_grade
                     else ("~" if ai_grade is not None and abs(ai_grade - manual_grade) <= 1
                           else "❌"))
        py_marker = ("✅" if py_grade == manual_grade
                     else ("~" if py_grade is not None and abs(py_grade - manual_grade) <= 1
                           else "❌"))

        print(f"  AI  {ai_marker} {ai_grade}   PY  {py_marker} {py_grade}"
              + (f"   [{flags}]" if flags else ""))

        result_rows.append({
            "HWID":    hwid,
            "Student": student_name,
            "Manual":  manual_grade,
            "AI":      ai_grade  if ai_grade  is not None else "ERR",
            "Python":  py_grade  if py_grade  is not None else "ERR",
            "Flags":   flags,
        })

    # ── Summary Report ────────────────────────────────────────────
    graded = sum(1 for r in result_rows if r["AI"] not in ("ERR",))

    def pct(n, d):
        return f"{n / d * 100:.1f}%" if d > 0 else "—"

    print()
    print("═" * 70)
    print("BENCHMARK ACCURACY REPORT")
    print("─" * 70)
    print(f"Submissions: {total} total | {graded} graded")
    print()
    print(f"  AI Agent  | Exact: {ai_exact} ({pct(ai_exact, graded)}) | "
          f"Within-1: {ai_within} ({pct(ai_within, graded)}) | "
          f"False rejects: {ai_fr} | False passes: {ai_fp}")
    print(f"  Python    | Exact: {py_exact} ({pct(py_exact, graded)}) | "
          f"Within-1: {py_within} ({pct(py_within, graded)}) | "
          f"False rejects: {py_fr} | False passes: {py_fp}")
    print("═" * 70)

    # ── Write outputs ─────────────────────────────────────────────
    write_results(RESULTS_CSV, result_rows)
    print(f"\nResults written to {RESULTS_CSV}")

    write_history_row(
        ai_exact, py_exact, ai_within, py_within,
        ai_fr, ai_fp, py_fr, py_fp, graded,
    )
    print(f"History row appended to benchmark_history.csv")


# ----------------------------------------------------------------
# Entry Point
# ----------------------------------------------------------------
if __name__ == "__main__":
    main()
