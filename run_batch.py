import logging
from bs4 import BeautifulSoup
from autograde_tools import autograde_homework_hybrid
from db_tools import (get_ungraded_homeworks,update_database_grade,insert_rejected_homework)
from email_tools import send_feedback_email, send_escalation_email

# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(message)s"
)

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def strip_html(html_text: str) -> str:
    """Convert HTML → clean text for database storage."""
    if not html_text:
        return ""
    text = BeautifulSoup(html_text, "html.parser").get_text(" ", strip=True)
    return " ".join(text.split())


# ------------------------------------------------------------
# Main Runner
# ------------------------------------------------------------
def main():
    logging.info("📌 Fetching ungraded items from vw_Homework (via db_tools)…")

    homeworks = get_ungraded_homeworks()
    logging.info(f"📌 Found {len(homeworks)} ungraded entries.\n")

    for hw in homeworks:
        hwid = hw.get("HomeworkID")
        logging.info(f"➡️ Grading HWID {hwid}")

        # ----------------------------------------------------
        # 1️⃣ Run Hybrid Autograder (v8)
        # ----------------------------------------------------
        result = autograde_homework_hybrid(hw)

        grade = int(result.get("grade", 1))
        comments_html = result.get("comments_html", "")
        feedback_html = result.get("feedback_html", "")
        escalate = result.get("escalate", False)
        escalation_reason = result.get("escalation_reason")
        grading_source = result.get("GradingSource", "Python")

        # ----------------------------------------------------
        # 2️⃣ Diagnostic logging
        # ----------------------------------------------------
        if result.get("ai_grade") is not None:
            logging.info(
                f"🤖 AI Grade: {result.get('ai_grade')} | "
                f"🧮 Python Grade: {result.get('python_grade')} | "
                f"🎯 Final Grade: {grade}"
            )
        else:
            logging.info("🧮 Python Grade only (no AI grade).")

        # ----------------------------------------------------
        # 3️⃣ Clean HTML for DB storage
        # ----------------------------------------------------
        clean_comments = strip_html(comments_html)
        clean_feedback = strip_html(feedback_html)

        # ----------------------------------------------------
        # 4️⃣ Persist + Notify (SINGLE CONTROL POINT)
        # ----------------------------------------------------
        answer_key = hw.get("AnswerKey")

        # 🚨 Guardrail: Missing AnswerKey → force manual review
        if not answer_key or str(answer_key).strip() == "":
            logging.warning(
                f"⚠️ HWID {hwid} missing AnswerKey — routed for manual review"
            )

            inserted = insert_rejected_homework(
                homework_id=hwid,
                grade=grade,
                comments=clean_comments,
                feedback=clean_feedback,
                escalate=True,
                escalation_reason="Answer key missing; manual review required",
                grading_source=grading_source,
                hw=hw
            )

            if inserted:
                send_escalation_email(hw, {
                    **result,
                    "escalate": True,
                    "escalation_reason": "Answer key missing; manual review required"
                })

            logging.info(
                f"🚨 HWID {hwid} | Missing AnswerKey → AUTOGRADER_REJECTS | Student email BLOCKED"
            )

        # 🚫 Low grades → reject table
        elif grade <= 2:
            inserted = insert_rejected_homework(
                homework_id=hwid,
                grade=grade,
                comments=clean_comments,
                feedback=clean_feedback,
                escalate=True,
                escalation_reason=escalation_reason,
                grading_source=grading_source,
                hw=hw
            )

            if inserted:
                send_escalation_email(hw, result)

            logging.info(
                f"🚨 HWID {hwid} | Grade {grade} routed to AUTOGRADER_REJECTS "
                f"| Student email BLOCKED"
            )

        # ✅ Normal grades → main table
        else:
            update_database_grade(
                homework_id=hwid,
                grade=grade,
                comments=clean_comments,
                feedback=clean_feedback,
                escalate=escalate,
                escalation_reason=escalation_reason,
                grading_source=grading_source,
                hw=hw
            )

            if escalate:
                send_escalation_email(hw, result)

            send_feedback_email(hw, grade, comments_html, feedback_html)

            logging.info(
                f"✅ HWID {hwid} | Grade {grade} updated in MAIN TABLE "
                f"| Student email SENT"
            )
# ------------------------------------------------------------
# Entry Point
# ------------------------------------------------------------
if __name__ == "__main__":
    main()