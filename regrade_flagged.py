import logging
from bs4 import BeautifulSoup
from autograde_agent import autograde_homework_agent
from db_tools import get_connection, update_database_grade, insert_rejected_homework
from email_tools import send_feedback_email, send_escalation_email

# ------------------------------------------------------------
# Logging — suppress INFO; silence httpx
# ------------------------------------------------------------
logging.basicConfig(level=logging.WARNING, format="%(levelname)s | %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

# ------------------------------------------------------------
# Flagged HomeworkIDs to force-regrade
# ------------------------------------------------------------
FLAGGED_HWIDS = [378086, 378100, 378101, 378109, 378128]

SOURCE_VIEW = "vw_Homework"


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def strip_html(html_text: str) -> str:
    """Convert HTML → clean text for database storage."""
    if not html_text:
        return ""
    text = BeautifulSoup(html_text, "html.parser").get_text(" ", strip=True)
    return " ".join(text.split())


def fetch_homework_by_id(hwid: int) -> dict | None:
    """Query ALL fields from vw_Homework for a single HomeworkID.
    No DateGraded filter — intentional for force-regrade."""
    conn = get_connection()
    if not conn:
        logging.error(f"No DB connection for HWID {hwid}")
        return None

    try:
        sql = f"SELECT * FROM {SOURCE_VIEW} WHERE HomeworkID = ?"
        cursor = conn.cursor()
        cursor.execute(sql, (hwid,))
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


# ------------------------------------------------------------
# Main Runner
# ------------------------------------------------------------
def main():
    summary = []  # rows: (hwid, student_name, original_grade, new_grade, status)

    for hwid in FLAGGED_HWIDS:
        print(f"\n➡️  Regrading HWID {hwid}")

        hw = fetch_homework_by_id(hwid)
        if hw is None:
            print(f"⚠️  HWID {hwid} | Not found — skipping")
            summary.append((hwid, "N/A", "N/A", "N/A", "not found"))
            continue

        student_name  = hw.get("StudentName", "Unknown")
        student_email = hw.get("StudentEmail", "")
        answer_key    = hw.get("AnswerKey")

        # Capture whatever grade is already stored in the view (may be None)
        original_grade = hw.get("Instr_Rating") or hw.get("Grade") or "—"

        print(f"   Student : {student_name}")
        print(f"   Email   : {student_email}")
        print(f"   Orig    : {original_grade}")

        # --------------------------------------------------------
        # 1️⃣ Run Agent Autograder
        # --------------------------------------------------------
        result = autograde_homework_agent(hw)

        grade             = int(result.get("grade", 1))
        comments_html     = result.get("comments_html", "")
        feedback_html     = result.get("feedback_html", "")
        escalate          = result.get("escalate", False)
        escalation_reason = result.get("escalation_reason")
        grading_source    = result.get("GradingSource", "Python")

        # --------------------------------------------------------
        # 2️⃣ Clean HTML for DB storage
        # --------------------------------------------------------
        clean_comments = strip_html(comments_html)
        clean_feedback = strip_html(feedback_html)

        # --------------------------------------------------------
        # 3️⃣ Persist + Notify — same routing as run_batch.py
        # --------------------------------------------------------

        # 🚨 Guardrail: Missing AnswerKey → force manual review
        if not answer_key or str(answer_key).strip() == "":
            reason = "Answer key missing; manual review required"
            print(f"🚨  HWID {hwid} | Grade {grade} | REJECTED | {reason}")

            inserted = insert_rejected_homework(
                homework_id=hwid,
                grade=grade,
                comments=clean_comments,
                feedback=clean_feedback,
                escalate=True,
                escalation_reason=reason,
                grading_source=grading_source,
                hw=hw,
            )

            if inserted:
                send_escalation_email(hw, {**result, "escalate": True, "escalation_reason": reason})
                print(f"📧  Escalation email sent to instructor")
                status = "escalated"
            else:
                status = "escalated (duplicate skipped)"

        # 🚫 Low grades → reject table
        elif grade <= 2:
            print(f"🚨  HWID {hwid} | Grade {grade} | REJECTED | {escalation_reason}")

            inserted = insert_rejected_homework(
                homework_id=hwid,
                grade=grade,
                comments=clean_comments,
                feedback=clean_feedback,
                escalate=True,
                escalation_reason=escalation_reason,
                grading_source=grading_source,
                hw=hw,
            )

            if inserted:
                send_escalation_email(hw, result)
                print(f"📧  Escalation email sent to instructor")
                status = "escalated"
            else:
                status = "escalated (duplicate skipped)"

        # ✅ Normal grades → main table
        else:
            print(f"✅  HWID {hwid} | Grade {grade} | Source: {grading_source}")

            update_database_grade(
                homework_id=hwid,
                grade=grade,
                comments=clean_comments,
                feedback=clean_feedback,
                escalate=escalate,
                escalation_reason=escalation_reason,
                grading_source=grading_source,
                hw=hw,
            )

            if escalate:
                send_escalation_email(hw, result)
                print(f"📧  Escalation email sent to instructor")
                status = "escalated + email sent"
            else:
                status = "email sent"

            send_feedback_email(hw, grade, comments_html, feedback_html)
            print(f"📧  Student email sent to {student_email}")

        summary.append((hwid, student_name, original_grade, grade, status))

    # ------------------------------------------------------------
    # Summary Table
    # ------------------------------------------------------------
    print()
    print("═" * 72)
    print(f"{'HWID':<10} {'StudentName':<22} {'Orig':>6} {'New':>5}  {'Status'}")
    print("─" * 72)
    for hwid, name, orig, new, status in summary:
        print(f"{hwid:<10} {name:<22} {str(orig):>6} {str(new):>5}  {status}")
    print("═" * 72)
    print(f"Regrade complete | {len(summary)} submission(s) processed")
    print("═" * 72)


# ------------------------------------------------------------
# Entry Point
# ------------------------------------------------------------
if __name__ == "__main__":
    main()
