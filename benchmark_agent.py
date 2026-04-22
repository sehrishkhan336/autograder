"""
benchmark_agent.py — Measure AI grader accuracy against a known-truth dataset.

Reads benchmark_truth.csv (columns: HomeworkID, ManualGrade, Notes),
fetches each homework from vw_Homework (read-only), runs the AI agent,
and reports accuracy statistics.

No DB writes. No emails sent.
"""

import csv
import logging
import os

from autograde_agent import autograde_homework_agent
from db_tools import get_connection

# ------------------------------------------------------------
# Logging — suppress INFO; silence httpx
# ------------------------------------------------------------
logging.basicConfig(level=logging.WARNING, format="%(levelname)s | %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

TRUTH_CSV   = "benchmark_truth.csv"
RESULTS_CSV = "benchmark_results.csv"
SOURCE_VIEW = "vw_Homework"


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def load_truth(path: str) -> list[dict]:
    """Read benchmark_truth.csv → list of dicts with HomeworkID, ManualGrade, Notes."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Truth file not found: {path}")

    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "HomeworkID":  int(row["HomeworkID"].strip()),
                "ManualGrade": int(row["ManualGrade"].strip()),
                "Notes":       row.get("Notes", "").strip(),
            })
    return rows


def fetch_homework_by_id(hwid: int) -> dict | None:
    """Query ALL fields from vw_Homework for a single HomeworkID. Read-only."""
    conn = get_connection()
    if not conn:
        logging.error(f"No DB connection for HWID {hwid}")
        return None

    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {SOURCE_VIEW} WHERE HomeworkID = ?", (hwid,))
        columns = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row is None:
            logging.warning(f"HWID {hwid} not found in {SOURCE_VIEW}")
            return None

        return dict(zip(columns, row))

    except Exception as e:
        logging.error(f"Error fetching HWID {hwid}: {e}")
        return None


def write_results(path: str, rows: list[dict]) -> None:
    """Write detailed per-submission results to a CSV file."""
    fieldnames = [
        "HomeworkID",
        "StudentName",
        "ManualGrade",
        "AIGrade",
        "ExactMatch",
        "WithinOne",
        "FalseReject",
        "FalsePass",
        "EscalatedByAI",
        "GradingSource",
        "Notes",
        "Error",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ------------------------------------------------------------
# Main Runner
# ------------------------------------------------------------
def main():
    truth_rows = load_truth(TRUTH_CSV)
    total = len(truth_rows)

    print(f"Loaded {total} entries from {TRUTH_CSV}\n")

    exact_count        = 0
    within_one_count   = 0
    false_reject_count = 0
    false_pass_count   = 0

    result_rows = []

    for entry in truth_rows:
        hwid         = entry["HomeworkID"]
        manual_grade = entry["ManualGrade"]
        notes        = entry["Notes"]

        print(f"➡️  HWID {hwid} | ManualGrade={manual_grade}")

        hw = fetch_homework_by_id(hwid)
        if hw is None:
            print(f"⚠️  HWID {hwid} | Not found in {SOURCE_VIEW} — skipping")
            result_rows.append({
                "HomeworkID":    hwid,
                "StudentName":   "N/A",
                "ManualGrade":   manual_grade,
                "AIGrade":       "",
                "ExactMatch":    "",
                "WithinOne":     "",
                "FalseReject":   "",
                "FalsePass":     "",
                "EscalatedByAI": "",
                "GradingSource": "",
                "Notes":         notes,
                "Error":         "not found in view",
            })
            continue

        student_name = hw.get("StudentName", "Unknown")

        # --------------------------------------------------------
        # Run AI agent — no DB writes, no emails
        # --------------------------------------------------------
        try:
            result = autograde_homework_agent(hw)
        except Exception as e:
            logging.error(f"HWID {hwid}: agent raised exception: {e}")
            result_rows.append({
                "HomeworkID":    hwid,
                "StudentName":   student_name,
                "ManualGrade":   manual_grade,
                "AIGrade":       "",
                "ExactMatch":    "",
                "WithinOne":     "",
                "FalseReject":   "",
                "FalsePass":     "",
                "EscalatedByAI": "",
                "GradingSource": "",
                "Notes":         notes,
                "Error":         str(e),
            })
            continue

        ai_grade      = int(result.get("grade", 1))
        grading_source = result.get("GradingSource", "")
        escalated     = bool(result.get("escalate", False))

        # --------------------------------------------------------
        # Accuracy metrics
        # --------------------------------------------------------
        exact        = ai_grade == manual_grade
        within_one   = abs(ai_grade - manual_grade) <= 1
        false_reject = manual_grade >= 3 and ai_grade <= 2
        false_pass   = manual_grade <= 2 and ai_grade >= 3

        if exact:
            exact_count += 1
        if within_one:
            within_one_count += 1
        if false_reject:
            false_reject_count += 1
        if false_pass:
            false_pass_count += 1

        marker = "✅" if exact else ("~" if within_one else "❌")
        fr_tag = " [FALSE REJECT]" if false_reject else ""
        fp_tag = " [FALSE PASS]"   if false_pass   else ""
        print(f"   {marker}  AI={ai_grade} | Manual={manual_grade}{fr_tag}{fp_tag}")

        result_rows.append({
            "HomeworkID":    hwid,
            "StudentName":   student_name,
            "ManualGrade":   manual_grade,
            "AIGrade":       ai_grade,
            "ExactMatch":    int(exact),
            "WithinOne":     int(within_one),
            "FalseReject":   int(false_reject),
            "FalsePass":     int(false_pass),
            "EscalatedByAI": int(escalated),
            "GradingSource": grading_source,
            "Notes":         notes,
            "Error":         "",
        })

    # Count only rows that were actually graded (no fetch error, no agent error)
    graded = sum(1 for r in result_rows if r["AIGrade"] != "")

    # ------------------------------------------------------------
    # Accuracy Report
    # ------------------------------------------------------------
    def pct(n: int, d: int) -> str:
        return f"{n / d * 100:.1f}%" if d > 0 else "—"

    print()
    print("═" * 68)
    print("BENCHMARK ACCURACY REPORT")
    print("─" * 68)
    print(
        f"Total: {total} | Graded: {graded} | "
        f"Exact: {exact_count} ({pct(exact_count, graded)}) | "
        f"Within-1: {within_one_count} ({pct(within_one_count, graded)}) | "
        f"False rejects: {false_reject_count} | "
        f"False passes: {false_pass_count}"
    )
    print("═" * 68)

    # ------------------------------------------------------------
    # Write detailed results
    # ------------------------------------------------------------
    write_results(RESULTS_CSV, result_rows)
    print(f"Detailed results written to {RESULTS_CSV}")


# ------------------------------------------------------------
# Entry Point
# ------------------------------------------------------------
if __name__ == "__main__":
    main()
