"""
review_rejects.py — Read-only report of the 9 most recent rows
in ADF_Homework_Autograder_Rejects.

Run:  python review_rejects.py
"""

from db_tools import get_connection, REJECT_TABLE

DIVIDER = "-" * 72


def main():
    conn = get_connection()
    if not conn:
        print("❌ Could not connect to the database.")
        return

    sql = f"""
        SELECT TOP 9
            HomeworkID,
            StudentName,
            SectionName,
            Instr_Rating,
            EscalationReason,
            HomeworkLink,
            DateProcessed
        FROM dbo.{REJECT_TABLE}
        ORDER BY DateProcessed DESC;
    """

    cursor = conn.cursor()
    cursor.execute(sql)
    rows = cursor.fetchall()
    columns = [col[0] for col in cursor.description]
    cursor.close()
    conn.close()

    records = [dict(zip(columns, row)) for row in rows]

    print(f"\n{'=' * 72}")
    print(f"  AUTOGRADER REJECTS REPORT  —  {REJECT_TABLE}")
    print(f"{'=' * 72}\n")

    for record in records:
        print(f"HomeworkID      : {record['HomeworkID']}")
        print(f"StudentName     : {record['StudentName']}")
        print(f"SectionName     : {record['SectionName']}")
        print(f"Grade Assigned  : {record['Instr_Rating']}")
        print(f"EscalationReason: {record['EscalationReason']}")
        print(f"HomeworkLink    : {record['HomeworkLink']}")
        print(f"DateProcessed   : {record['DateProcessed']}")
        print(DIVIDER)

    print(f"\nTotal shown: {len(records)}\n")


if __name__ == "__main__":
    main()
