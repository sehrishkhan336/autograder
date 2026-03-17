import os
import logging
import pyodbc
from dotenv import load_dotenv


load_dotenv()

REJECT_TABLE = "ADF_Homework_Autograder_Rejects"

# ---------------------------------------------------------------------
# Load DB credentials
# ---------------------------------------------------------------------
DB_SERVER = os.getenv("DB_SERVER")
DB_DATABASE = os.getenv("DB_DATABASE")
DB_USERNAME = os.getenv("DB_USERNAME")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_TRUSTED = os.getenv("DB_TRUSTED", "no").lower() == "yes"

SOURCE_VIEW = "vw_Homework"        # read-only view
TEST_TABLE = "ADF_Homework_test"   # write-only table

IGNORE_SOURCE_FILTERS = os.getenv("IGNORE_SOURCE_FILTERS", "no").lower() == "yes"

# ---------------------------------------------------------------------
# SQL Connection Helper
# ---------------------------------------------------------------------
def get_connection():
    """Connect to SQL Server using Windows Auth OR SQL Auth."""
    try:
        if DB_TRUSTED:
            conn_str = (
                "Driver={ODBC Driver 17 for SQL Server};"
                f"Server={DB_SERVER};"
                f"Database={DB_DATABASE};"
                "Trusted_Connection=yes;"
            )
        else:
            conn_str = (
                "Driver={ODBC Driver 17 for SQL Server};"
                f"Server={DB_SERVER};"
                f"Database={DB_DATABASE};"
                f"UID={DB_USERNAME};"
                f"PWD={DB_PASSWORD};"
                "TrustServerCertificate=yes;"
            )

        conn = pyodbc.connect(conn_str)
        logging.info(f"✅ Connected to {DB_SERVER}/{DB_DATABASE}")
        return conn

    except Exception as e:
        logging.error(f"❌ DB connection failed: {e}")
        return None


# ---------------------------------------------------------------------
# 1️⃣ Fetch Ungraded Homeworks (MINIMAL fields only)
# ---------------------------------------------------------------------
def get_ungraded_homeworks(limit=50):
    """Returns rows from vw_Homework with only fields needed by autograder."""

    conn = get_connection()
    if not conn:
        return []

    try:
        sql = f"""
            SELECT TOP ({limit})
                HomeworkID,
                HomeworkLink,
                AnswerKey,
                SectionID,
                StudentEmail,
                StudentUserID,   -- from view
                StudentName,
                SectionName,
                ClassSignupsID
            FROM {SOURCE_VIEW}
            WHERE DateGraded IS NULL
              AND DateEntered IS NOT NULL
              AND StudentName IS NOT NULL
            ORDER BY DateEntered;
        """

        cursor = conn.cursor()
        cursor.execute(sql)

        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        cursor.close()
        conn.close()

        logging.info(f"📌 Pulled {len(rows)} ungraded homeworks from vw_Homework")
        return rows

    except Exception as e:
        logging.error(f"❌ Error fetching from vw_Homework: {e}")
        return []


# ---------------------------------------------------------------------
# 2️⃣ Insert Graded Result into ADF_Homework_test (Production-Ready)
# ---------------------------------------------------------------------
def update_database_grade(
    homework_id,
    grade,
    comments,
    feedback,
    escalate,
    escalation_reason,
    grading_source=None,
    hw=None
):
    """Inserts graded homework into ADF_Homework_test table."""
    try:
        hw = hw or {}

        conn = get_connection()
        cursor = conn.cursor()

        if grade >= 4:
            flag_color = "🟢"
        elif grade == 3:
            flag_color = "🟡"
        else:
            flag_color = "🔴"

        sql = """
            INSERT INTO dbo.ADF_Homework_test (
                 HomeworkID,
                ClassSignupsID,
                SectionID,
                StudentUserID,
                StudentName,
                StudentEmail,
                SectionName,
                HomeworkLink,
                AnswerKey,
                Instr_Comments,
                Instr_Rating,
                Feedback,
                GradingSource,
                EscalationReason,
                EscalateFlag,
                DateProcessed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE());
        """

        params = (
            homework_id,
            hw.get("ClassSignupsID"),
            hw.get("SectionID"),
            hw.get("StudentUserID"),
            hw.get("StudentName"),
            hw.get("StudentEmail"),
            hw.get("SectionName"),
            hw.get("HomeworkLink"),
            hw.get("AnswerKey"),
            comments,
            grade,
            feedback,
            grading_source,
            escalation_reason,
            int(escalate)
        )

        cursor.execute(sql, params)
        conn.commit()
        cursor.close()
        conn.close()

        logging.info(f"📌 Inserted HWID {homework_id} into ADF_Homework_test")

    except Exception as e:
        logging.error(f"❌ DB insert error for HWID {homework_id}: {e}")


def insert_rejected_homework(
    homework_id,
    grade,
    comments,
    feedback,
    escalate,
    escalation_reason,
    grading_source=None,
    hw=None
):
    """
    Inserts grade 1–2 homework into ADF_Homework_Autograder_Rejects.
    Safe to re-run batch multiple times (idempotent).
    """
    try:
        hw = hw or {}

        conn = get_connection()
        cursor = conn.cursor()

        # -------------------------------------------------
        # Idempotency check (HomeworkID + StudentUserID)
        # -------------------------------------------------
        check_sql = f"""
            SELECT 1
            FROM dbo.{REJECT_TABLE}
            WHERE HomeworkID = ?
              AND StudentUserID = ?
        """

        cursor.execute(
            check_sql,
            (homework_id, hw.get("StudentUserID"))
        )

        if cursor.fetchone():
            logging.warning(
                f"⚠️ Duplicate reject skipped for HWID {homework_id} "
                f"(StudentUserID={hw.get('StudentUserID')})"
            )
            cursor.close()
            conn.close()
            return False

        # -------------------------------------------------
        # Insert reject record
        # -------------------------------------------------
        sql = f"""
            INSERT INTO dbo.{REJECT_TABLE} (
                HomeworkID,
                ClassSignupsID,
                SectionID,
                StudentUserID,
                StudentName,
                StudentEmail,
                SectionName,
                HomeworkLink,
                AnswerKey,
                Instr_Comments,
                Instr_Rating,
                Feedback,
                GradingSource,
                Escalate,
                EscalationReason,
                DateProcessed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE());
        """

        params = (
            homework_id,
            hw.get("ClassSignupsID"),
            hw.get("SectionID"),
            hw.get("StudentUserID"),
            hw.get("StudentName"),
            hw.get("StudentEmail"),
            hw.get("SectionName"),
            hw.get("HomeworkLink"),
            hw.get("AnswerKey"),
            comments,
            grade,
            feedback,
            grading_source,
            int(escalate),
            escalation_reason
        )

        cursor.execute(sql, params)
        conn.commit()
        cursor.close()
        conn.close()

        logging.info(
            f"🚫 HWID {homework_id} inserted into {REJECT_TABLE} "
            f"(grade={grade}, escalated)"
        )
        return True

    except Exception as e:
        logging.error(
            f"❌ Reject insert failed for HWID {homework_id}: {e}"
        )
        return False
# ----------------------------------------------------------------------