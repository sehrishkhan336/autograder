import os
import logging
import pyodbc
from dotenv import load_dotenv


load_dotenv()

REJECT_TABLE = "ADF_Homework_Autograder_Rejects"
REJECT_TEST_TABLE = "ADF_Homework_Autograder_Rejects_test"
MAIN_TEST_TABLE = "ADF_Homework_test"

# ---------------------------------------------------------------------
# Load DB credentials
# ---------------------------------------------------------------------
DB_SERVER = os.getenv("DB_SERVER")
DB_DATABASE = os.getenv("DB_DATABASE")
DB_USERNAME = os.getenv("DB_USERNAME")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_TRUSTED = os.getenv("DB_TRUSTED", "no").lower() == "yes"
USE_TEST_SOURCE = os.getenv("USE_TEST_SOURCE", "no").lower() == "yes"

SOURCE_VIEW = "vw_Homework"        # read-only view
TEST_TABLE = MAIN_TEST_TABLE       # write-only table

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
        logging.info(f"âœ… Connected to {DB_SERVER}/{DB_DATABASE}")
        return conn

    except Exception as e:
        logging.error(f"âŒ DB connection failed: {e}")
        return None


def _normalize_confidence(confidence):
    """Return confidence as a 0.0-1.0 float, defaulting unknown values to 0.0."""
    if confidence is None:
        return 0.0
    try:
        return max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        logging.warning(f"Invalid AI confidence ignored: {confidence!r}")
        return 0.0


def _ensure_ai_confidence_column(cursor, table_name):
    """
    Ensure a nullable AIConfidence column exists before inserting.
    This keeps test-table schema drift from breaking batch persistence.
    """
    sql = f"""
        IF COL_LENGTH('dbo.{table_name}', 'AIConfidence') IS NULL
        BEGIN
            ALTER TABLE dbo.{table_name}
            ADD AIConfidence FLOAT NULL;
        END
    """
    cursor.execute(sql)


# ---------------------------------------------------------------------
# 1ï¸âƒ£ Fetch Ungraded Homeworks (MINIMAL fields only)
# ---------------------------------------------------------------------
def get_ungraded_homeworks(limit=50):
    """Returns rows for autograder. Source switches on USE_TEST_SOURCE env flag."""

    conn = get_connection()
    if not conn:
        return []

    try:
        if USE_TEST_SOURCE:
            sql = f"""
                SELECT TOP ({limit})
                    HomeworkID,
                    HomeworkLink,
                    AnswerKey,
                    SectionID,
                    StudentEmail,
                    StudentUserID,
                    StudentName,
                    SectionName,
                    ClassSignupsID,
                    EscalationReason
                FROM dbo.ADF_Homework_test
                WHERE Instr_Rating IS NULL
                  AND EscalationReason LIKE 'OriginalHWID=%%'
                ORDER BY DateProcessed DESC
            """
        else:
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

        if USE_TEST_SOURCE:
            logging.info(f"ðŸ“Œ Pulled {len(rows)} homeworks from ADF_Homework_test (TEST MODE)")
        else:
            logging.info(f"ðŸ“Œ Pulled {len(rows)} ungraded homeworks from vw_Homework")
        return rows

    except Exception as e:
        logging.error(f"âŒ Error fetching from vw_Homework: {e}")
        return []


# ---------------------------------------------------------------------
# 2ï¸âƒ£ Insert Graded Result into ADF_Homework_test (Production-Ready)
# ---------------------------------------------------------------------
def update_database_grade(
    homework_id,
    grade,
    comments,
    feedback,
    escalate,
    escalation_reason,
    grading_source=None,
    hw=None,
    confidence=None,
):
    """Inserts graded homework into ADF_Homework_test table."""
    try:
        hw = hw or {}
        confidence = _normalize_confidence(confidence)

        conn = get_connection()
        cursor = conn.cursor()
        _ensure_ai_confidence_column(cursor, MAIN_TEST_TABLE)

        if grade >= 4:
            flag_color = "ðŸŸ¢"
        elif grade == 3:
            flag_color = "ðŸŸ¡"
        else:
            flag_color = "ðŸ”´"

        sql = """
            INSERT INTO dbo.ADF_Homework_test (
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
                AIConfidence,
                DateProcessed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE());
        """

        params = (
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
            int(escalate),
            confidence,
        )

        cursor.execute(sql, params)
        conn.commit()
        cursor.close()
        conn.close()

        logging.info(f"ðŸ“Œ Inserted HWID {homework_id} into ADF_Homework_test")

    except Exception as e:
        logging.error(f"âŒ DB insert error for HWID {homework_id}: {e}")


def insert_rejected_homework(
    homework_id,
    grade,
    comments,
    feedback,
    escalate,
    escalation_reason,
    grading_source=None,
    hw=None,
    confidence=None,
):
    """
    Inserts grade 1â€“2 homework into ADF_Homework_Autograder_Rejects.
    Safe to re-run batch multiple times (idempotent).
    """
    try:
        hw = hw or {}
        confidence = _normalize_confidence(confidence)

        conn = get_connection()
        cursor = conn.cursor()
        _ensure_ai_confidence_column(cursor, REJECT_TEST_TABLE)

        # -------------------------------------------------
        # Idempotency check (HomeworkID + StudentUserID)
        # -------------------------------------------------
        check_sql = f"""
            SELECT 1
            FROM dbo.{REJECT_TEST_TABLE}
            WHERE HomeworkID = ?
              AND StudentUserID = ?
        """

        cursor.execute(
            check_sql,
            (homework_id, hw.get("StudentUserID"))
        )

        if cursor.fetchone():
            logging.warning(
                f"âš ï¸ Duplicate reject skipped for HWID {homework_id} "
                f"(StudentUserID={hw.get('StudentUserID')})"
            )
            cursor.close()
            conn.close()
            return False

        # -------------------------------------------------
        # Insert reject record
        # -------------------------------------------------
        sql = f"""
            INSERT INTO dbo.{REJECT_TEST_TABLE} (
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
                AIConfidence,
                DateProcessed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE());
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
            escalation_reason,
            confidence,
        )

        cursor.execute(sql, params)
        conn.commit()
        cursor.close()
        conn.close()

        logging.info(
            f"ðŸš« HWID {homework_id} inserted into {REJECT_TEST_TABLE} "
            f"(grade={grade}, escalated)"
        )
        return True

    except Exception as e:
        logging.error(
            f"âŒ Reject insert failed for HWID {homework_id}: {e}"
        )
        return False
# ----------------------------------------------------------------------
