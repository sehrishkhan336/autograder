import os
import json
import requests
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()
FORCE_SEND_EMAIL = os.getenv("FORCE_SEND_EMAIL", "no").lower() == "yes"

# GLOBAL SAFETY LOCK
if not FORCE_SEND_EMAIL:
    print("❌ FORCE_SEND_EMAIL=no — ALL EMAILS DISABLED")

# ----------------------------------------------------------------------
# ENV VARIABLES (Must be in .env)
# ----------------------------------------------------------------------
MANDRILL_API_KEY = os.getenv("MANDRILL_API_KEY")
MANDRILL_API_URL = os.getenv("MANDRILL_API_URL", "https://mandrillapp.com/api/1.0/messages/send.json")

EMAIL_SENDER = os.getenv("EMAIL_SENDER")     # cai@colaberry.com
#FORCE_SEND_EMAIL = os.getenv("FORCE_SEND_EMAIL", "no").lower() == "yes"
EMAIL_DRY_RUN = os.getenv("EMAIL_DRY_RUN", "no").lower() == "yes"


# Instructor escalation email from .env
ESCALATION_EMAIL = os.getenv("ESCALATION_EMAIL")   # ali@colaberry.com
ESCALATION_HOMEWORKS_URL = os.getenv(
    "ESCALATION_HOMEWORKS_URL",
    "https://app.colaberry.com/app/training/homeworks"  # safe fallback
)


# ----------------------------------------------------------------------
# Build Student Email (HTML)
# ----------------------------------------------------------------------
def build_student_html(hw, grade, comments_html, feedback_html):
    student_name = hw.get("StudentName", "Student")
    assignment = hw.get("SectionName", "Assignment")
    course = hw.get("SectionName", "Course") 

    link = hw.get("HomeworkLink", "")
    

    return f"""
    <p>Hello {student_name},</p>

    <p>Your submission for <b>{assignment}</b> has been graded.</p>
    <p><b>Grade:</b> {grade}/5</p>

    <p><b>Comments:</b></p>
    {comments_html}

    <p><b>Feedback:</b></p>
    {feedback_html}

    {f'<p><b>Homework Link:</b> <a href="{link}">{link}</a></p>' if int(grade) != 5 else ''}

    <p>
        <b>Course:</b> {course}<br>
        <b>Instructor:</b> Mentor Team
    </p>

    <p>Thank you,<br>
    Mentor<br>
    Colaberry School of Data Analytics</p>
    """


# ----------------------------------------------------------------------
# SEND STUDENT EMAIL (Mandrill)
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# SEND STUDENT EMAIL (Mandrill)
# ----------------------------------------------------------------------
def send_feedback_email(hw, grade, comments_html, feedback_html):
    """
    Sends student email ONLY.
    Instructor escalation is handled by send_escalation_email().
    """

    # 🔒 HARD GUARDRAIL — never email grades 1–2
    if int(grade) <= 2:
        print(f"🚫 Student email BLOCKED by guardrail (grade={grade})")
        return

    to_email = os.getenv("STUDENT_EMAIL", "").strip()
    if not to_email:
        print("⚠️ No student email found — cannot send student email.")
        return

    # DRY RUN MODE
    if EMAIL_DRY_RUN:
        print("\n📧 [DRY RUN] Would send student email to:", to_email)
        return

    # Safety toggle
    if not FORCE_SEND_EMAIL:
        print("\n📧 [SAFE MODE] FORCE_SEND_EMAIL=no — student email NOT sent.")
        return

    html_body = build_student_html(hw, grade, comments_html, feedback_html)

    payload = {
        "key": MANDRILL_API_KEY,
        "message": {
            "from_email": EMAIL_SENDER,
            "to": [{"email": to_email, "type": "to"}],
            "subject": f"Your Homework Grade — {grade}/5",
            "html": html_body
        }
    }


    # Send via Mandrill
    try:
        res = requests.post(MANDRILL_API_URL, json=payload)
        print("\n📧 Student Email Sent:")
        print(json.dumps(res.json(), indent=2))
    except Exception as e:
        print(f"❌ Student email sending error: {e}")



# ----------------------------------------------------------------------
# BUILD ESCALATION EMAIL HTML
# ----------------------------------------------------------------------
def build_escalation_html(hw, result):
    student = hw.get("StudentName")
    email = hw.get("STUDENT_EMAIL") #revert to StudentEmail when ready for implementation
    hwid = hw.get("HomeworkID")
    section = hw.get("SectionName")
    escalation_link = ESCALATION_HOMEWORKS_URL
    grade = result.get("grade")
    reason = result.get("escalation_reason")

    return f"""
    <p>Hello Instructor,</p>

    <p>
    The autograder has identified a homework submission that requires
    <b>manual review</b>. Below are the key details for your reference:
    </p>    

    <ul>
        <li><b>Homework ID:</b> {hwid}</li>
        <li><b>Student Name:</b> {student}</li>
        <li><b>Student Email:</b> {email}</li>
        <li><b>Section:</b> {section}</li>
        <li><b>Assigned Grade:</b> {grade}/5</li>
        <li><b>Escalation Reason:</b> {reason}</li>
        <li><b>Escalation Link:</b> <a href="{escalation_link}">{escalation_link}</a></li>
    </ul>

    <p>
    The preliminary grade above was assigned through automated evaluation
    and is provided for reference only.
    Please review the submission and adjust the grade as needed based on
    manual assessment.
    </p>

    <p>Thank you for your time and support.</p>

    <p>Best Regards,<br>
    Autograder System</p>
    """


# ----------------------------------------------------------------------
# SEND INSTRUCTOR ESCALATION EMAIL
# ----------------------------------------------------------------------
def send_escalation_email(hw, result):
    """Send escalation email to instructor when autograder flags escalate=True."""

    if not result.get("escalate"):
        return  # Nothing to escalate

    if not ESCALATION_EMAIL:
        print("⚠️ ESCALATION_EMAIL missing in .env — escalation skipped.")
        return

    if EMAIL_DRY_RUN:
        print(f"\n📧 [DRY RUN] Would send escalation email to: {ESCALATION_EMAIL}")
        return

    if not FORCE_SEND_EMAIL:
        print("\n📧 [SAFE MODE] FORCE_SEND_EMAIL=no — escalation email NOT sent.")
        return

    html_body = build_escalation_html(hw, result)

    payload = {
        "key": MANDRILL_API_KEY,
        "message": {
            "from_email": EMAIL_SENDER,
            "to": [{"email": ESCALATION_EMAIL, "type": "to"}],
            "subject": f"⚠️ Manual Review Needed — HWID {hw.get('HomeworkID')}",
            "html": html_body
        }
    }


    # Send via Mandrill
    try:
        res = requests.post(MANDRILL_API_URL, json=payload)
        print("\n📧 Escalation Email Sent:")
        print(json.dumps(res.json(), indent=2))
    except Exception as e:
        print(f"❌ Escalation email sending error: {e}")
"""Returns rows from vw_Homework with only fields needed by autograder."""