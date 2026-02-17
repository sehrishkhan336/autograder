"""
Autograder v8 (Hybrid AI + Python) — Unified Messaging

NON-NEGOTIABLE RULE (v8):
Comments and feedback must NEVER depend on grading source (AI vs Python).
They must depend ONLY on:
  - Final grade
  - Assignment type (SQL vs DOCX vs Paragraph)
  - Optional context (missing ops, partial ops, screenshot count, paragraph count)

Paragraph-based assignments:
  - Evaluated on the availability/presence of paragraphs (NOT correctness).
"""

import os
import re
import json
import tempfile
import zipfile
import logging
from typing import Dict, Any, Tuple, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

try:
    import docx  # python-docx
except ImportError:
    docx = None
    logging.warning("python-docx is not installed; DOCX grading will be limited.")

logger = logging.getLogger(__name__)

# ============================================================
# ENV: AI GRADE-ONLY (HYBRID MODE)
# ============================================================

ENABLE_AI_GRADING = os.getenv("ENABLE_AI_GRADING", "no").lower() == "yes"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
AI_TIMEOUT_SECS = int(os.getenv("AI_TIMEOUT_SECS", "60"))
OPENAI_RESPONSES_URL = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/responses")
AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.2"))
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "1000"))

# ============================================================
# SQL PATTERNS
# ============================================================

SQL_OPS: Dict[str, str] = {
    "select": r"\bselect\b",
    "from": r"\bfrom\b",
    "where": r"\bwhere\b",
    "group_by": r"\bgroup\s+by\b",
    "having": r"\bhaving\b",
    "aggregate_sum": r"\bsum\s*\(",
    "aggregate_avg": r"\bavg\s*\(",
    "aggregate_count": r"\bcount\s*\(",
    "aggregate_min": r"\bmin\s*\(",
    "aggregate_max": r"\bmax\s*\(",
    "join": r"\b(join|inner\s+join|left\s+join|right\s+join|full\s+join|cross\s+join)\b",
    "order_by": r"\border\s+by\b",
    "insert_into": r"\binsert\s+into\b",
    "update": r"\bupdate\b",
    "delete": r"\bdelete\b",
    "create_table": r"\bcreate\s+table\b",
    "alter_table": r"\balter\s+table\b",
    "declare": r"\bdeclare\b",
    "set": r"\bset\b",
    "create_func": r"\bcreate\s+function\b",
    "create_proc": r"\bcreate\s+proc(?:edure)?\b",
    "cte": r"\bwith\s+[A-Za-z0-9_]+\s+as\s*\(",
    "subquery": r"\(\s*select\b",
    "case": r"\bcase\b",
    "implicit_join": r"from\s+\w+\s*,\s*\w+",
    "distinct": r"\bdistinct\b",
}

# ============================================================
# SQL HELPERS
# ============================================================

def _strip_sql_comments(sql: str) -> str:
    """Remove single-line and multi-line comments from SQL text."""
    sql = re.sub(r"--.*", "", sql)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.S)
    return sql

def _count_pattern(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text, flags=re.IGNORECASE))

def _extract_sql_requirements(answer_sql: str) -> Dict[str, int]:
    """From answer key SQL, determine which SQL operations are required."""
    clean = _strip_sql_comments(answer_sql.lower())
    req: Dict[str, int] = {}
    for op, pattern in SQL_OPS.items():
        cnt = _count_pattern(pattern, clean)
        if cnt > 0:
            req[op] = cnt
    return req

def _measure_student_sql_coverage(
    student_sql: str,
    requirements: Dict[str, int],
) -> Tuple[float, Dict[str, float]]:
    """
    Binary presence logic:
      coverage[op] = 1.0 if op appears at least once, else 0.0
    """
    clean = _strip_sql_comments(student_sql.lower())
    if not requirements:
        return 0.0, {}

    coverage: Dict[str, float] = {}
    for op in requirements.keys():
        stu_count = _count_pattern(SQL_OPS[op], clean)
        coverage[op] = 1.0 if stu_count >= 1 else 0.0

    overall = round(sum(coverage.values()) / len(coverage), 2)
    return overall, coverage

def _map_score_to_grade(score: float) -> int:
    """
    Thresholds:
      >= 0.60 → 5
      >= 0.40 → 4
      >= 0.20 → 3
      >= 0.10 → 2
      else   → 1
    """
    if score >= 0.60:
        return 5
    if score >= 0.40:
        return 4
    if score >= 0.20:
        return 3
    if score >= 0.10:
        return 2
    return 1

# ============================================================
# ZIP / DOWNLOAD HELPERS
# ============================================================

def download_file(url: str) -> Optional[str]:
    if not url:
        return None
    local = tempfile.mktemp()
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with open(local, "wb") as f:
            f.write(r.content)
        return local
    except Exception as e:
        logger.warning(f"Download failed: {e}")
        return None

def inspect_zip_extensions(zip_path: Optional[str]) -> List[str]:
    if not zip_path:
        return []
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            exts = []
            for name in z.namelist():
                if "." in name:
                    exts.append(name.split(".")[-1].lower())
            return exts
    except Exception:
        return []

def extract_sql_from_zip(zip_path: Optional[str]) -> str:
    if not zip_path:
        return ""
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            for name in z.namelist():
                if name.lower().endswith(".sql"):
                    return z.open(name).read().decode(errors="ignore")
    except Exception:
        pass
    return ""

# ============================================================
# DOCX HELPERS
# ============================================================

def _extract_docx_from_zip(zip_path: str) -> Tuple[str, int]:
    """
    Return (text, image_count) from the FIRST .docx in the ZIP.
    If python-docx not available or parsing fails, returns ("", 0).
    """
    if not docx:
        return "", 0

    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            for name in z.namelist():
                if name.lower().endswith(".docx"):
                    tmp_path = tempfile.mktemp(suffix=".docx")
                    with z.open(name) as src, open(tmp_path, "wb") as dst:
                        dst.write(src.read())
                    d = docx.Document(tmp_path)
                    text = "\n".join(p.text for p in d.paragraphs)
                    image_count = len(d.inline_shapes)
                    return text, image_count
    except Exception as e:
        logger.warning(f"Error extracting DOCX from ZIP: {e}")

    return "", 0

def _count_nonempty_paragraphs(doc_text: str) -> int:
    lines = [ln.strip() for ln in (doc_text or "").split("\n")]
    nonempty = [ln for ln in lines if ln]
    return len(nonempty)

# ============================================================
# COMMENTS & FEEDBACK TEMPLATES (GRADE-BASED)
# ============================================================

def _generate_comments_html_sql(grade: int, missing_ops: List[str], partial_ops: List[str]) -> str:
    bullets: List[str] = []

    if grade == 5:
        bullets.append("🌟 Excellent SQL work! Your solution includes all key SQL components expected for this lab.")
        return "<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>"

    if grade == 4:
        bullets.append("👍 Very good SQL work with a few areas to refine.")
        if missing_ops:
            bullets.append(f"⚠️ Minor missing SQL elements: {', '.join(missing_ops)}")
        if partial_ops:
            bullets.append(f"🛠️ Partially implemented: {', '.join(partial_ops)}")
        bullets.append("💡 Review these parts in the answer key to reach a perfect score next time.")
        return "<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>"

    if grade == 3:
        bullets.append("🛠️ Good attempt, but several required SQL concepts are incomplete.")
    else:
        bullets.append("⚠️ Many key SQL components are missing or incorrect.")

    if missing_ops:
        bullets.append(f"❌ Missing SQL operations: {', '.join(missing_ops)}")
    if partial_ops:
        bullets.append(f"⚠️ Partially implemented SQL operations: {', '.join(partial_ops)}")

    bullets.append("💡 Revisit the lab video and answer key, and make sure each required step is present in your SQL.")
    return "<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>"

def _generate_comments_html_docx(grade: int, stu_imgs: int, escalation: Optional[str] = None) -> str:
    if escalation:
        return (
            "<ul>"
            f"<li>🙋‍♀️ Manual review suggested: {escalation}</li>"
            "<li>💡 Please check the assignment instructions and update your document/screenshots.</li>"
            "</ul>"
        )

    if grade == 5:
        return (
            "<ul>"
            "<li>🌟 Great job documenting your work!</li>"
            f"<li>📸 We found {stu_imgs} screenshots, which meets or exceeds the recommended minimum of 3.</li>"
            "<li>✅ Your submission structure looks complete and easy to follow.</li>"
            "</ul>"
        )

    if grade == 4:
        return (
            "<ul>"
            "<li>👍 Strong documentation overall with minor improvements needed.</li>"
            f"<li>📸 Screenshots found: {stu_imgs}. Recommended: at least 3 covering all major steps.</li>"
            "<li>💡 Add 1–2 more key screenshots to strengthen your submission.</li>"
            "</ul>"
        )

    if grade == 3:
        return (
            "<ul>"
            "<li>🛠️ Nice effort! Your document includes some screenshots, but a few key steps may be missing.</li>"
            f"<li>📸 Screenshots found: {stu_imgs}. Recommended: at least 3 that cover all main steps.</li>"
            "<li>💡 Try to include a screenshot for each major step in the lab instructions next time.</li>"
            "</ul>"
        )

    return (
        "<ul>"
        "<li>⚠️ Documentation is incomplete or missing required screenshots.</li>"
        "<li>❌ We could not verify the lab steps from the submitted file.</li>"
        "<li>💡 Please follow the lab template, add the screenshots, and resubmit for a higher grade.</li>"
        "</ul>"
    )

def _generate_comments_html_paragraph(grade: int, paragraph_count: int) -> str:
    # Paragraph-based assignments: presence/availability, not correctness
    if grade == 5:
        return (
            "<ul>"
            "<li>🌟 Great job! Your written response is present and clearly structured.</li>"
            f"<li>✅ Paragraphs found: {paragraph_count}</li>"
            "</ul>"
        )
    if grade == 4:
        return (
            "<ul>"
            "<li>👍 Strong written submission. A bit more detail or structure would make it even better.</li>"
            f"<li>✅ Paragraphs found: {paragraph_count}</li>"
            "</ul>"
        )
    if grade == 3:
        return (
            "<ul>"
            "<li>🛠️ A written response is present, but it appears brief or missing some expected sections.</li>"
            f"<li>✅ Paragraphs found: {paragraph_count}</li>"
            "<li>💡 Add more detail and make sure each required prompt/section has its own paragraph.</li>"
            "</ul>"
        )
    return (
        "<ul>"
        "<li>⚠️ We could not find the required written response in the submitted document.</li>"
        f"<li>✅ Paragraphs found: {paragraph_count}</li>"
        "<li>💡 Please add the required paragraphs and resubmit.</li>"
        "</ul>"
    )

def _generate_feedback_html(grade: int, is_sql: bool) -> str:
    tips_sql = [
        "💡 Tip: Practice writing queries step by step and test each part in SSMS.",
        "💡 Tip: Focus on JOINs and GROUP BY — they appear often in real projects.",
        "💡 Tip: Use clear aliases and avoid SELECT * to make your queries easier to read."
    ]

    tips_doc = [
        "📘 Tip: Add short captions under screenshots to explain what each step shows.",
        "📘 Tip: Make sure your screenshots are large and clear enough to read.",
        "📘 Tip: Follow the assignment order so your document tells a clear story."
    ]

    tip_list = tips_sql if is_sql else tips_doc
    tip = tip_list[grade % len(tip_list)]

    if grade >= 4:
        main = (
            "<ul>"
            "<li>🌟 Excellent effort! You're building strong skills — keep going.</li>"
            "<li>🚀 Continue practicing similar labs to make this feel even more natural.</li>"
            "</ul>"
        )
    elif grade == 3:
        main = (
            "<ul>"
            "<li>👍 Good progress! With a bit more attention to the missing parts, your work will improve quickly.</li>"
            "<li>🧠 Keep practicing and reviewing the solution — you're on the right track.</li>"
            "</ul>"
        )
    else:
        main = (
            "<ul>"
            "<li>🌱 This is a starting point — don't be discouraged.</li>"
            "<li>🔍 Re-watch the lab video and compare your work to the answer key step by step.</li>"
            "</ul>"
        )

    return main + f"<p>{tip}</p>"

# ============================================================
# FINAL (UNIFIED) COMMENT/FEEDBACK BUILDER — v8 RULE
# ============================================================

def build_final_comments_and_feedback(
    *,
    final_grade: int,
    assignment_type: str,  # "sql" | "docx" | "paragraph"
    sql_missing_ops: Optional[List[str]] = None,
    sql_partial_ops: Optional[List[str]] = None,
    screenshot_count: Optional[int] = None,
    paragraph_count: Optional[int] = None,
) -> Tuple[str, str]:
    """
    Single source of truth: final grade + assignment type + context -> comments + feedback
    NEVER depends on grading source.
    """
    sql_missing_ops = sql_missing_ops or []
    sql_partial_ops = sql_partial_ops or []
    screenshot_count = screenshot_count or 0
    paragraph_count = paragraph_count or 0

    if assignment_type == "sql":
        comments_html = _generate_comments_html_sql(final_grade, sql_missing_ops, sql_partial_ops)
        feedback_html = _generate_feedback_html(final_grade, is_sql=True)
        return comments_html, feedback_html

    if assignment_type == "paragraph":
        comments_html = _generate_comments_html_paragraph(final_grade, paragraph_count)
        feedback_html = _generate_feedback_html(final_grade, is_sql=False)
        return comments_html, feedback_html

    # default: docx screenshots
    comments_html = _generate_comments_html_docx(final_grade, stu_imgs=screenshot_count)
    feedback_html = _generate_feedback_html(final_grade, is_sql=False)
    return comments_html, feedback_html

# ============================================================
# AI GRADE ONLY (RETURNS DICT CONSISTENTLY)
# ============================================================

def _ai_grade_only(hw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Calls OpenAI and returns:
      {"grade": int|None, "parsed_cleanly": bool, "raw_text": str}
    Returns None if AI disabled or fails hard.
    """
    if not ENABLE_AI_GRADING:
        logger.info("🤖 AI grading disabled via ENABLE_AI_GRADING.")
        return None
    if not OPENAI_API_KEY:
        logger.warning("🤖 OPENAI_API_KEY missing — AI grading skipped.")
        return None

    prompt = f"""
You are an experienced instructor grading student homework.

Return ONLY a single integer from 1 to 5.
Do NOT explain your answer.

Grading philosophy (lenient on minor issues):
- 5 = Complete and correct (all required tasks present; logic correct)
- 4 = Mostly complete and correct (all main requirements met; minor mistakes/inefficiencies OK)
- 3 = Clearly incomplete (major required parts missing OR results largely incorrect)
- 2 = Minimal attempt (very limited progress)
- 1 = Empty/placeholder/irrelevant

IMPORTANT:
- If the work looks mostly complete, choose 4 instead of 3.
- Do NOT drop to 3 for minor syntax, formatting, or inefficiency.

Homework context:
HomeworkID: {hw.get("HomeworkID")}
SectionName: {hw.get("SectionName")}
HomeworkLink: {hw.get("HomeworkLink")}
AnswerKey: {hw.get("AnswerKey") or hw.get("Answerkey")}
""".strip()

    try:
        payload = {
            "model": OPENAI_MODEL,
            "input": prompt,
            "temperature": AI_TEMPERATURE,
            "max_output_tokens": AI_MAX_TOKENS,
        }
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }

        logger.info("🤖 Calling OpenAI for grade-only evaluation…")
        response = requests.post(
            OPENAI_RESPONSES_URL,
            headers=headers,
            json=payload,
            timeout=AI_TIMEOUT_SECS,
        )
        response.raise_for_status()
        data = response.json()

        text_candidates: List[str] = []
        if isinstance(data.get("output_text"), str):
            text_candidates.append(data["output_text"])

        for item in data.get("output", []):
            for content in item.get("content", []):
                if isinstance(content, dict) and "text" in content:
                    text_candidates.append(content["text"])

        for txt in text_candidates:
            raw = (txt or "").strip()
            if raw.isdigit():
                g = int(raw)
                if 1 <= g <= 5:
                    logger.info(f"🤖 AI returned grade: {g}")
                    return {"grade": g, "parsed_cleanly": True, "raw_text": raw}

        logger.warning("🤖 AI response received but no valid grade found.")
        return {"grade": None, "parsed_cleanly": False, "raw_text": " | ".join(text_candidates)[:500]}

    except Exception as e:
        logger.error(f"🤖 AI grading failed: {e}")
        return None

def _ai_grade_to_int(ai_result: Optional[Dict[str, Any]]) -> Optional[int]:
    if not ai_result:
        return None
    g = ai_result.get("grade")
    try:
        return int(g) if g is not None else None
    except Exception:
        return None

# ============================================================
# DELTA LOGGING + RECONCILIATION (FIXED)
# ============================================================

def log_grade_delta(homework_id: Any, ai: Optional[int], py: int, final: int) -> None:
    try:
        delta = None if ai is None else (py - ai)
        logger.info(
            f"📊 GRADE DELTA | HW={homework_id} | AI={ai} | PY={py} | FINAL={final} | DELTA(py-ai)={delta}"
        )
    except Exception:
        logger.exception("Failed to log grade delta")

# ============================================================
# DOCX GRADERS (STRUCTURE ONLY)
# ============================================================

def _grade_docx_screenshot_structure(stu_zip: str) -> Dict[str, Any]:
    """
    Screenshot-based structure rules:
      ✔ DOCX exists AND ≥5 screenshots → Grade 5
      ✔ DOCX exists AND 3–4 screenshots → Grade 4
      ✔ DOCX exists AND 1–2 screenshots → Grade 3
      ✔ DOCX exists AND text only       → Grade 2
      ❌ No DOCX text AND no screenshots → Grade 1, escalate
    Returns context only; unified messaging done later from FINAL grade.
    """
    text, img_count = _extract_docx_from_zip(stu_zip)
    para_count = _count_nonempty_paragraphs(text)

    # Nothing submitted at all
    if para_count == 0 and img_count == 0:
        return {
            "grade": 1,
            "assignment_type": "docx",
            "screenshot_count": 0,
            "paragraph_count": 0,
            "escalate": True,
            "escalation_reason": "DOCX file contains no screenshots or written explanation."
        }

    # Text exists but no screenshots → minimal attempt
    if img_count == 0:
        return {
            "grade": 2,
            "assignment_type": "docx",
            "screenshot_count": 0,
            "paragraph_count": para_count,
            "escalate": False,
            "escalation_reason": None
        }

    # Screenshots present
    if img_count >= 5:
        grade = 5
    elif img_count >= 3:
        grade = 4
    else:  # 1–2 screenshots
        grade = 3

    return {
        "grade": grade,
        "assignment_type": "docx",
        "screenshot_count": img_count,
        "paragraph_count": para_count,
        "escalate": False,
        "escalation_reason": None
    }

def _grade_paragraph_presence_structure(stu_zip: str) -> Dict[str, Any]:
    """
    Paragraph-based assignments (presence/availability only; NOT correctness).
    Heuristic thresholds:
      - >= 4 non-empty paragraphs → 5
      - >= 3 paragraphs → 4
      - >= 2 paragraphs → 3
      - == 1 paragraph  → 2
      - 0 → 1 (escalate)
    """
    text, img_count = _extract_docx_from_zip(stu_zip)
    para_count = _count_nonempty_paragraphs(text)

    if para_count >= 4:
        grade = 5
        escalate = False
        reason = None
    elif para_count >= 3:
        grade = 4
        escalate = False
        reason = None
    elif para_count >= 2:
        grade = 3
        escalate = False
        reason = None
    elif para_count == 1:
        grade = 2
        escalate = False
        reason = None
    else:
        grade = 1
        escalate = True
        reason = "Required written response missing (no paragraphs found)."

    return {
        "grade": grade,
        "assignment_type": "paragraph",
        "screenshot_count": img_count,
        "paragraph_count": para_count,
        "escalate": escalate,
        "escalation_reason": reason
    }

# ============================================================
# PERFORMANCE-BASED ESCALATION (kept)
# ============================================================

def _check_performance_escalation(hw: Dict[str, Any], current_grade: int) -> Tuple[bool, Optional[str]]:
    recent = hw.get("RecentGrades") or hw.get("recent_grades")
    if not recent or not isinstance(recent, (list, tuple)) or len(recent) < 2:
        return False, None

    last_two = list(recent)[:2]
    try:
        last_two_int = [int(g) for g in last_two]
    except Exception:
        return False, None

    if all(g < 3 for g in last_two_int) and current_grade < 3:
        reason = (
            "Student has received grades below 3 on the last two homeworks and on this one. "
            "Recommend instructor review for additional support."
        )
        return True, reason

    return False, None

def _apply_performance_escalation(hw: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    if result.get("escalate"):
        return result

    g = int(result.get("grade", 1))
    escalate, reason = _check_performance_escalation(hw, g)
    if escalate:
        result["escalate"] = True
        result["escalation_reason"] = (
            f"{result['escalation_reason']} | {reason}" if result.get("escalation_reason") else reason
        )
    return result

# ============================================================
# PYTHON GRADER (STRUCTURE + CONTEXT ONLY)
# ============================================================

def autograde_homework(hw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Python-only grading (structure + deterministic checks).
    IMPORTANT (v8): This function returns structure/context ONLY.
    Student-facing comments/feedback are generated AFTER final grade is known.
    """
    stu_url = hw.get("HomeworkLink")
    ans_url = hw.get("AnswerKey") or hw.get("Answerkey")

    if not stu_url:
        base = {
            "grade": 1,
            "assignment_type": "unknown",
            "escalate": True,
            "escalation_reason": "Missing HomeworkLink URL."
        }
        return _apply_performance_escalation(hw, base)

    if not stu_url.lower().endswith(".zip"):
        base = {
            "grade": 1,
            "assignment_type": "unknown",
            "escalate": True,
            "escalation_reason": "Submission is not a ZIP file."
        }
        return _apply_performance_escalation(hw, base)

    stu_zip = download_file(stu_url)
    if not stu_zip:
        base = {
            "grade": 1,
            "assignment_type": "unknown",
            "escalate": True,
            "escalation_reason": "Student ZIP download failed."
        }
        return _apply_performance_escalation(hw, base)

    ans_zip = download_file(ans_url) if ans_url else None
    stu_exts = inspect_zip_extensions(stu_zip)
    ans_exts = inspect_zip_extensions(ans_zip) if ans_zip else []

    # --------------------------------------------------------
    # SQL ASSIGNMENTS (answer key has .sql)
    # --------------------------------------------------------
    if "sql" in ans_exts:
        if "sql" not in stu_exts:
            base = {
                "grade": 1,
                "assignment_type": "sql",
                "sql_missing_ops": [],
                "sql_partial_ops": [],
                "escalate": True,
                "escalation_reason": "Missing SQL file in submission."
            }
            return _apply_performance_escalation(hw, base)

        stu_sql = extract_sql_from_zip(stu_zip)
        ans_sql = extract_sql_from_zip(ans_zip)

        if not stu_sql.strip():
            base = {
                "grade": 1,
                "assignment_type": "sql",
                "sql_missing_ops": [],
                "sql_partial_ops": [],
                "escalate": True,
                "escalation_reason": "Empty or unreadable SQL in submission."
            }
            return _apply_performance_escalation(hw, base)

        if not ans_sql.strip():
            base = {
                "grade": 1,
                "assignment_type": "sql",
                "sql_missing_ops": [],
                "sql_partial_ops": [],
                "escalate": True,
                "escalation_reason": "Answer key SQL missing/unavailable."
            }
            return _apply_performance_escalation(hw, base)

        requirements = _extract_sql_requirements(ans_sql)
        score, coverage = _measure_student_sql_coverage(stu_sql, requirements)
        grade = _map_score_to_grade(score)

        missing = [op for op, v in coverage.items() if v == 0.0]
        partial = [op for op, v in coverage.items() if 0.0 < v < 1.0]

        base = {
            "grade": grade,
            "assignment_type": "sql",
            "score": score,
            "sql_missing_ops": missing,
            "sql_partial_ops": partial,
            "escalate": grade <= 2,
            "escalation_reason": "Low SQL concept coverage." if grade <= 2 else None,
        }
        logger.info("🧮 Python grading completed (hybrid reconciliation may follow).")
        return _apply_performance_escalation(hw, base)

    # --------------------------------------------------------
    # DOCX / SCREENSHOT or PARAGRAPH assignments
    # --------------------------------------------------------
    if "docx" in ans_exts or "docx" in stu_exts:
        # Decide paragraph vs screenshot:
        # If docx exists but no screenshots, treat as paragraph-based (presence only)
        text, img_count = _extract_docx_from_zip(stu_zip)

        if text.strip() and img_count == 0:
            base = _grade_paragraph_presence_structure(stu_zip)
            logger.info("🧮 Python grading completed (hybrid reconciliation may follow).")
            return _apply_performance_escalation(hw, base)

        base = _grade_docx_screenshot_structure(stu_zip)
        logger.info("🧮 Python grading completed (hybrid reconciliation may follow).")
        return _apply_performance_escalation(hw, base)

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------
    base = {
        "grade": 1,
        "assignment_type": "unknown",
        "escalate": True,
        "escalation_reason": "Unrecognized submission/answer-key format."
    }
    logger.info("🧮 Python grading completed (hybrid reconciliation may follow).")
    return _apply_performance_escalation(hw, base)

# ============================================================
# HYBRID GRADER (FINAL GRADE + UNIFIED MESSAGING)
# ============================================================

def autograde_homework_hybrid(hw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Hybrid grading (v8 – hardened):

      1) Python computes structure/context grade (authoritative for structure)
      2) If structure is INVALID → AI is completely skipped
      3) If structure is VALID → AI computes advisory grade-only
      4) Reconcile to FINAL grade
      5) Generate comments/feedback from FINAL grade + assignment type + context
    """

    # ----------------------------------------------------
    # 1️⃣ Python grading (STRUCTURE AUTHORITY)
    # ----------------------------------------------------
    py_result = autograde_homework(hw)
    python_grade = int(py_result.get("grade", 1))
    assignment_type = py_result.get("assignment_type", "unknown")
    escalate = bool(py_result.get("escalate", False))
    escalation_reason = py_result.get("escalation_reason")
    # ----------------------------------------------------
    # 🚨 HARD SAFETY GATE — STRUCTURE ALWAYS WINS
    # ----------------------------------------------------
    if not py_result.get("structural_valid", True):
        logging.warning(
            f"🚫 Structural failure detected — skipping AI grading for HWID {hw.get('HomeworkID')}"
        )

        comments_html, feedback_html = build_final_comments_and_feedback(
            final_grade=python_grade,
            assignment_type=assignment_type,
            sql_missing_ops=py_result.get("sql_missing_ops"),
            sql_partial_ops=py_result.get("sql_partial_ops"),
            screenshot_count=py_result.get("screenshot_count"),
            paragraph_count=py_result.get("paragraph_count"),
        )

        return {
            "grade": python_grade,
            "GradingSource": "Python",


            "comments_html": comments_html,
            "feedback_html": feedback_html,
            "escalate": bool(py_result.get("escalate", False)),
            "escalation_reason": py_result.get("escalation_reason"),
            "python_grade": python_grade,
            "ai_grade": None,
            "assignment_type": assignment_type,
        }

    # ----------------------------------------------------
    # 2️⃣ AI advisory grading (ONLY if structure is valid)
    # ----------------------------------------------------
    ai_result = _ai_grade_only(hw)
    ai_grade = _ai_grade_to_int(ai_result)

    # ----------------------------------------------------
    # 3️⃣ Reconcile final grade
    # ----------------------------------------------------
    final_grade = python_grade
    log_grade_delta(hw.get("HomeworkID"), ai_grade, python_grade, python_grade)


      
    # ----------------------------------------------------
    # 5️⃣ Unified comments & feedback (FINAL grade only)
    # ----------------------------------------------------
    comments_html, feedback_html = build_final_comments_and_feedback(
        final_grade=final_grade,
        assignment_type=assignment_type,
        sql_missing_ops=py_result.get("sql_missing_ops"),
        sql_partial_ops=py_result.get("sql_partial_ops"),
        screenshot_count=py_result.get("screenshot_count"),
        paragraph_count=py_result.get("paragraph_count"),
    )

    return {
        "grade": final_grade,
        "GradingSource": "Python (AI-reviewed)",
        "comments_html": comments_html,
        "feedback_html": feedback_html,
        "escalate": escalate,
        "escalation_reason": escalation_reason,
        "python_grade": python_grade,
        "ai_grade": ai_grade,
        "assignment_type": assignment_type,
    }

