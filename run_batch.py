import logging
from bs4 import BeautifulSoup
from autograde_tools import autograde_homework_hybrid
from autograde_agent import autograde_homework_agent
from db_tools import (get_ungraded_homeworks, update_database_grade, insert_rejected_homework)
from email_tools import send_feedback_email, send_escalation_email

# ------------------------------------------------------------
# Logging — suppress INFO from all modules; silence httpx
# ------------------------------------------------------------
logging.basicConfig(level=logging.WARNING, format="%(levelname)s | %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

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
    homeworks = get_ungraded_homeworks()
    total    = len(homeworks)
    passed   = 0
    rejected = 0

    for hw in homeworks:
        hwid          = hw.get("HomeworkID")
        student_name  = hw.get("StudentName", "Unknown")
        section_name  = hw.get("SectionName", "Unknown")
        student_email = hw.get("StudentEmail", "")

        print(f"➡️  HWID {hwid} | {student_name} | {section_name}")

        # ----------------------------------------------------
        # 1️⃣ Run Agent Autograder (primary)
        # ----------------------------------------------------
        result = autograde_homework_agent(hw)

        grade             = int(result.get("grade", 1))
        comments_html     = result.get("comments_html", "")
        feedback_html     = result.get("feedback_html", "")
        escalate          = result.get("escalate", False)
        escalation_reason = result.get("escalation_reason")
        grading_source    = result.get("GradingSource", "Python")

        # ----------------------------------------------------
        # 2️⃣ Hybrid grader (shadow run — comparison only)
        # ----------------------------------------------------
        try:
            hybrid_result = autograde_homework_hybrid(hw)
            hybrid_grade  = int(hybrid_result.get("grade", 1))
            delta         = hybrid_grade - grade
            print(f"🔬  Shadow: Agent={grade} | Hybrid={hybrid_grade} | Delta={delta:+d}")
        except Exception:
            pass

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
                hw=hw
            )

            if inserted:
                send_escalation_email(hw, {
                    **result,
                    "escalate": True,
                    "escalation_reason": reason
                })
                print(f"📧  Escalation email sent to instructor")

            rejected += 1

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
                hw=hw
            )

            if inserted:
                send_escalation_email(hw, result)
                print(f"📧  Escalation email sent to instructor")

            rejected += 1

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
                hw=hw
            )

            if escalate:
                send_escalation_email(hw, result)
                print(f"📧  Escalation email sent to instructor")

            send_feedback_email(hw, grade, comments_html, feedback_html)
            print(f"📧  Student email sent to {student_email}")

            passed += 1

    print()
    print("════════════════════════════════")
    print(f"Batch complete | Total: {total} | Passed: {passed} | Rejected: {rejected}")
    print("════════════════════════════════")


# ------------------------------------------------------------
# Entry Point
# ------------------------------------------------------------
if __name__ == "__main__":
    main()
