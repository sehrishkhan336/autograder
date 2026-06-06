"""
build_benchmark_input.py
========================
ONE-TIME script to generate benchmark_input.csv from TestingManualGrading.xlsx.
Run once, commit benchmark_input.csv to git, never modify manually.

Usage: python build_benchmark_input.py
Output: benchmark_input.csv

Grade mapping:
  "5-accepted"  → 5
  "4-accepted"  → 4
  "3-accepted"  → 3
  "0-Rejected"  → 1  (no real work = grade 1)
  "0-Rectected" → 1  (typo in source, same rule)
"""

import csv
import os
import sys
from collections import Counter

try:
    import openpyxl
except ImportError:
    print("ERROR: openpyxl not installed. Run: pip install openpyxl")
    sys.exit(1)

EXCEL_FILE = "TestingManualGrading.xlsx"
OUTPUT_CSV = "benchmark_input.csv"


def parse_manual_grade(raw: str) -> int:
    if not raw:
        raise ValueError("Empty grade value")
    cleaned = str(raw).strip().lower()
    if cleaned.startswith("0") or "reject" in cleaned:
        return 1
    for digit in ["5", "4", "3", "2", "1"]:
        if cleaned.startswith(digit):
            return int(digit)
    raise ValueError(f"Cannot parse grade: {repr(raw)}")


def main():
    if not os.path.exists(EXCEL_FILE):
        print(f"ERROR: {EXCEL_FILE} not found in project root.")
        sys.exit(1)

    wb = openpyxl.load_workbook(EXCEL_FILE, read_only=True)
    ws = wb["Sheet1"]
    all_rows = list(ws.iter_rows(values_only=True))
    data_rows = all_rows[2:]  # row 0=blank, row 1=header, row 2+ = data

    output = []
    errors = []

    print(f"\nReading {EXCEL_FILE}...\n")
    print(f"{'HWID':<10} {'Student':<25} {'Grade Raw':<18} {'Parsed':<8} {'HW Link Present':<18} {'AK Present'}")
    print("-" * 100)

    for row in data_rows:
        _, hwid, student, section, raw_grade, hw_link, answer_key, comments = row
        if not hwid:
            continue
        try:
            grade = parse_manual_grade(str(raw_grade) if raw_grade else "")
        except ValueError as e:
            errors.append(f"HWID {hwid}: {e}")
            grade = None

        hw_ok = "YES" if hw_link else "MISSING"
        ak_ok = "YES" if answer_key else "MISSING"
        print(f"{str(hwid):<10} {str(student):<25} {str(raw_grade):<18} {str(grade):<8} {hw_ok:<18} {ak_ok}")

        output.append({
            "HomeworkID": hwid,
            "StudentName": student,
            "SectionName": section,
            "ManualGrade": grade,
            "HomeworkLink": hw_link or "",
            "AnswerKey": answer_key or "",
            "Notes": str(comments or "").strip(),
        })

    if errors:
        print(f"\nERRORS — fix before saving:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)

    dist = Counter(r["ManualGrade"] for r in output)
    print(f"\nGrade distribution: " + " | ".join(f"Grade {g}={dist[g]}" for g in [1,2,3,4,5]))
    print(f"Total rows: {len(output)}")

    missing_hw = [r["HomeworkID"] for r in output if not r["HomeworkLink"]]
    missing_ak = [r["HomeworkID"] for r in output if not r["AnswerKey"]]
    if missing_hw:
        print(f"WARNING: Missing HomeworkLink: {missing_hw}")
    if missing_ak:
        print(f"WARNING: Missing AnswerKey: {missing_ak}")

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["HomeworkID","StudentName","SectionName",
                                                "ManualGrade","HomeworkLink","AnswerKey","Notes"])
        writer.writeheader()
        writer.writerows(output)

    print(f"\nWritten: {OUTPUT_CSV} ({len(output)} rows)")


if __name__ == "__main__":
    main()
