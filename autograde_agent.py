"""
autograde_agent.py — OpenAI tool-use agent for semantic homework grading.

The public entry point is autograde_homework_agent(hw: dict) -> dict.
Its return shape is identical to autograde_homework_hybrid() so
run_batch.py requires zero changes to switch between the two.
"""

import json
import logging
import os
from typing import Any, Callable, Dict, Optional, Tuple

from openai import OpenAI
from dotenv import load_dotenv

from file_tools import (
    download_file,
    inspect_zip_extensions,
    extract_sql_from_zip,
    _extract_docx_from_zip,
    _count_nonempty_paragraphs,
)

load_dotenv()

logger = logging.getLogger(__name__)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
MAX_AGENT_TURNS = 12  # hard ceiling on tool-use rounds

# ============================================================
# TOOL DEFINITIONS
# ============================================================
# Stored in Anthropic input_schema format; converted to OpenAI
# function schema at runtime inside autograde_homework_agent().

TOOLS = [
    {
        "name": "fetch_submission",
        "description": (
            "Download the student's ZIP submission from the provided URL and extract its "
            "content. For SQL assignments the full SQL text is returned. For DOCX assignments "
            "the document text, screenshot count, and paragraph count are returned. "
            "Must be called before validate_format or finalize_grade."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The student's HomeworkLink URL pointing to a ZIP file."
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "fetch_answer_key",
        "description": (
            "Download the answer key ZIP from the provided URL and extract its content. "
            "For SQL assignments the full SQL text is returned so you can compare it "
            "directly against the student's submission. "
            "Must be called before validate_format or finalize_grade."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The AnswerKey URL pointing to a ZIP file."
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "validate_format",
        "description": (
            "Validate that the student submission contains the file types required by the "
            "answer key (e.g. .sql or .docx). Returns whether validation passed, which "
            "types are required, which the student provided, and any that are missing. "
            "Must be called after both fetch_submission and fetch_answer_key."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "finalize_grade",
        "description": (
            "Record the final grade and student-facing feedback. Call this only after "
            "fetching both ZIPs, validating format, and completing a semantic comparison "
            "of the student's submission against the answer key. "
            "comments_html and feedback_html must be personalized HTML that references "
            "the student's specific work — not generic placeholders. "
            "Set confidence to 0.9+ when certain, 0.7–0.8 when mostly sure, "
            "0.5 or below when uncertain (ambiguous submission or borderline grade)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "grade": {
                    "type": "integer",
                    "description": "Final grade from 1 to 5."
                },
                "comments_html": {
                    "type": "string",
                    "description": (
                        "HTML <ul><li>...</li></ul> comments describing what the student "
                        "did correctly or incorrectly, referencing their actual submission "
                        "content (e.g. specific clauses used, screenshots present)."
                    )
                },
                "feedback_html": {
                    "type": "string",
                    "description": (
                        "HTML with actionable improvement tips personalized to this "
                        "student's specific gaps or strengths."
                    )
                },
                "escalate": {
                    "type": "boolean",
                    "description": "True if this submission requires manual instructor review."
                },
                "escalation_reason": {
                    "type": "string",
                    "description": (
                        "Brief reason for manual review. Required when escalate is true, "
                        "otherwise omit or pass null."
                    )
                },
                "confidence": {
                    "type": "number",
                    "description": (
                        "Grading confidence from 0.0 to 1.0. "
                        "Return 0.9+ when certain, 0.7–0.8 when mostly sure, "
                        "0.5 or below when uncertain."
                    )
                }
            },
            "required": ["grade", "comments_html", "feedback_html", "escalate", "confidence"]
        }
    },
    {
        "name": "validate_with_python",
        "description": (
            "Run the Python structural grader as a second opinion. Use this when your "
            "confidence is 0.7 or below, or when you want to sanity-check a borderline "
            "grade before finalizing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]

# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """You are an expert data analytics instructor grading student homework submissions.

========== WORKFLOW (follow this order every time) ==========

1. Call fetch_submission with the student's submission URL.
2. Call fetch_answer_key with the answer key URL.
3. Call validate_format to confirm the submission contains the required file types.
   - If validation fails → immediately call finalize_grade with grade=1, escalate=true,
     and a brief escalation_reason. Do not proceed further.
4. Read ALL content returned carefully — across ALL submitted files.
5. Compare the student's work semantically against the answer key content.
6. Write personalized comments_html and feedback_html referencing the student's actual work.
7. Call finalize_grade with your final evaluation.

========== FORMAT VALIDATION (hard failures) ==========

- Answer key requires .sql AND student has zero .sql files → grade=1, escalate=true.
- Answer key requires .docx AND student has zero .docx files → grade=1, escalate=true.
- All SQL content across every submitted file is empty → grade=1, escalate=true.
- Multiple .sql files are ACCEPTABLE — read and grade them together as one submission.
- Multiple .docx files are ACCEPTABLE — review all of them together.

========== GRADING SCALE ==========

- 5 = All required tasks present and logically correct.
- 4 = Mostly complete; all main requirements met; minor mistakes or inefficiencies OK.
- 3 = Major required parts missing OR results largely incorrect.
- 2 = Minimal attempt; submission is nearly empty or placeholder only.
- 1 = Empty, wrong format, or format validation failed.

========== SQL GRADING CRITERIA ==========

You are grading for CORRECTNESS and CONCEPT COVERAGE — not answer
key matching. The student may solve the problem any valid way they
choose. Two solutions that produce the same result are equally valid
even if written differently.

WHAT TO GRADE ON:
- Does the student's solution address the question being asked?
- Are the required SQL concepts for this homework present and used
  correctly? Base this on what the answer key uses as a signal of
  what concepts are required — not as the only valid solution.
- Is the logic correct? (correct table, correct filter, correct
  aggregation, correct grouping)

REQUIRED CONCEPT DETECTION (use answer key as a guide):
- If answer key uses GROUP BY → student must demonstrate grouping
  (GROUP BY or equivalent)
- If answer key uses aggregate functions (SUM, AVG, COUNT, MIN, MAX)
  → student must use the same category of aggregate
- If answer key uses JOIN → student must join tables (any valid JOIN
  type is acceptable)
- If answer key uses HAVING → student may use HAVING or WHERE
  depending on context — evaluate whether their filter achieves
  the correct result
- If answer key uses subquery → student may use subquery OR CTE OR
  JOIN to achieve same result — all are valid
- If answer key uses DECLARE/SET → student must use variables

WHAT NOT TO PENALIZE:
- Different but valid SQL syntax (INNER JOIN vs JOIN)
- Different column aliases
- Different spacing, formatting, or comment style
- Different order of clauses (as long as SQL is valid)
- Extra queries or additional exploration beyond what was asked
- Using a CTE instead of a subquery or vice versa
- Using HAVING instead of WHERE when both produce correct results

GRADING SCALE APPLIED TO SQL:
- 5 = All required concepts present, logic is correct
- 4 = All required concepts present, minor logic gaps or one
      small mistake
- 3 = Most required concepts present but key logic is wrong or
      a major concept is missing
- 2 = Few required concepts present, mostly incomplete
- 1 = No meaningful SQL or format validation failed

========== DOCX GRADING CRITERIA ==========

- Check that key lab steps are documented with screenshots.
- Check that paragraph count covers the required sections.
- Be lenient on writing style and formatting.

========== ESCALATION RULES (critical) ==========

- escalate=true ONLY when final grade is 1 or 2.
- NEVER escalate grade 3, 4, or 5 — grade 3+ means the student did meaningful work.

========== STUDENT-FACING RULES (critical) ==========

- NEVER mention the answer key or that one exists.
- NEVER expose internal scoring rules, formulas, or system logic.
- NEVER mention structural validators or autograder behavior.
- comments_html and feedback_html must only describe what is missing and how to improve,
  using references to the lab instructions and lab steps.
- Always use a friendly, encouraging tone.
- Always use HTML tags (<ul>, <li>, <p>) in comments_html and feedback_html.

========== CONFIDENCE SCORING ==========

Set confidence based on how clearly the submission maps to a grade:
- 0.9–1.0: Clear pass or clear fail — submission is unambiguous (e.g. all concepts
  present and correct, or empty/wrong-format file).
- 0.7–0.8: Mostly sure but minor ambiguity (e.g. one required concept is unclear
  or a query is partially correct).
- 0.5–0.6: Borderline grade; submission could reasonably be one grade higher or lower
  (e.g. incomplete but shows real effort, or logic is close but not quite right).
- 0.0–0.4: Very uncertain — submission is highly ambiguous, uses an unusual approach
  that is hard to evaluate, or content is too sparse to judge fairly.

========== PYTHON VALIDATION ==========

When your confidence is below 0.7, you MUST call validate_with_python before finalize_grade.
- validate_with_python runs deterministic structural checks: SQL pattern matching,
  required file presence, screenshot count, and paragraph count.
- Its grade is advisory only — you make the final grading decision based on your
  full semantic evaluation of the submission.
- If the Python grade differs from your intended grade by 2 or more, briefly note
  why in escalation_reason so an instructor can review if needed.
"""

# ============================================================
# TOOL EXECUTOR (closure-based state)
# ============================================================

def _make_executor(hw: Dict[str, Any]) -> Tuple[Callable, Callable]:
    """
    Build the tool executor for one grading session.
    State (downloaded zip paths, final result) is held in a closure.
    Returns (execute_tool, get_result).
    """
    state: Dict[str, Any] = {
        "submission_zip": None,
        "answer_key_zip": None,
        "final_result": None,
    }

    def _extract_zip_content(zip_path: str) -> Dict[str, Any]:
        """Read all relevant content from a downloaded ZIP and return as a dict."""
        exts = inspect_zip_extensions(zip_path)
        result: Dict[str, Any] = {"file_types": exts}

        if "sql" in exts:
            sql_text = extract_sql_from_zip(zip_path)
            result["sql_content"] = sql_text if sql_text.strip() else "(empty)"

        if "docx" in exts:
            text, img_count = _extract_docx_from_zip(zip_path)
            para_count = _count_nonempty_paragraphs(text)
            result["docx_text"] = text if text.strip() else "(empty)"
            result["screenshot_count"] = img_count
            result["paragraph_count"] = para_count

        return result

    def execute_tool(tool_name: str, tool_input: Dict[str, Any]) -> str:

        # ── fetch_submission ────────────────────────────────────────────
        if tool_name == "fetch_submission":
            url = tool_input.get("url", "")
            zip_path = download_file(url)
            if not zip_path:
                return json.dumps({"error": "Download failed.", "url": url})
            state["submission_zip"] = zip_path
            return json.dumps(_extract_zip_content(zip_path))

        # ── fetch_answer_key ────────────────────────────────────────────
        if tool_name == "fetch_answer_key":
            url = tool_input.get("url", "")
            zip_path = download_file(url)
            if not zip_path:
                return json.dumps({"error": "Download failed.", "url": url})
            state["answer_key_zip"] = zip_path
            return json.dumps(_extract_zip_content(zip_path))

        # ── validate_format ─────────────────────────────────────────────
        if tool_name == "validate_format":
            stu_zip = state.get("submission_zip")
            ans_zip = state.get("answer_key_zip")
            if not stu_zip or not ans_zip:
                return json.dumps({
                    "valid": False,
                    "error": "fetch_submission and fetch_answer_key must be called first."
                })
            stu_exts = set(inspect_zip_extensions(stu_zip))
            ans_exts = set(inspect_zip_extensions(ans_zip))
            required = ans_exts & {"sql", "docx"}
            missing = sorted(required - stu_exts)
            return json.dumps({
                "valid": len(missing) == 0,
                "required_types": sorted(required),
                "student_types": sorted(stu_exts),
                "missing_types": missing,
            })

        # ── finalize_grade ──────────────────────────────────────────────
        if tool_name == "finalize_grade":
            raw_grade = tool_input.get("grade", 1)
            grade = max(1, min(5, int(raw_grade)))
            escalate = bool(tool_input.get("escalate", False))
            # Enforce escalation for very low grades
            if grade <= 2:
                escalate = True
            raw_confidence = tool_input.get("confidence", 0.5)
            confidence = max(0.0, min(1.0, float(raw_confidence)))
            state["final_result"] = {
                "grade": grade,
                "comments_html": tool_input.get("comments_html", ""),
                "feedback_html": tool_input.get("feedback_html", ""),
                "escalate": escalate,
                "escalation_reason": tool_input.get("escalation_reason") or None,
                "confidence": confidence,
                "GradingSource": "OpenAI-agent",
            }
            return json.dumps({"status": "grade recorded", "grade": grade})

        # ── validate_with_python ────────────────────────────────────────
        if tool_name == "validate_with_python":
            from autograde_tools import autograde_homework  # lazy import — avoids circular risk
            try:
                py_result = autograde_homework(hw)
                return json.dumps({
                    "python_grade":     py_result.get("grade"),
                    "assignment_type":  py_result.get("assignment_type"),
                    "structural_valid": py_result.get("structural_valid"),
                    "escalate":         py_result.get("escalate"),
                    "escalation_reason": py_result.get("escalation_reason"),
                    "sql_missing_ops":  py_result.get("sql_missing_ops", []),
                    "score":            py_result.get("score"),
                })
            except Exception as e:
                return json.dumps({"error": f"Python grader failed: {e}"})

        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    def get_result() -> Optional[Dict[str, Any]]:
        return state["final_result"]

    return execute_tool, get_result


# ============================================================
# AGENT LOOP
# ============================================================

def autograde_homework_agent(hw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Grade a homework submission using an OpenAI tool-use agent loop.

    Returns a dict with keys:
        grade, comments_html, feedback_html, escalate, escalation_reason, GradingSource

    Shape is identical to autograde_homework_hybrid() — run_batch.py needs no changes.
    """
    hwid = hw.get("HomeworkID")
    stu_url = hw.get("HomeworkLink", "")
    ans_url = hw.get("AnswerKey") or hw.get("Answerkey", "")

    fallback: Dict[str, Any] = {
        "grade": 1,
        "comments_html": (
            "<ul><li>Your submission could not be graded automatically at this time.</li></ul>"
        ),
        "feedback_html": (
            "<ul><li>Please contact your instructor for assistance with this submission.</li></ul>"
        ),
        "escalate": True,
        "escalation_reason": "Agent grading failed — manual review required.",
        "GradingSource": "OpenAI-agent (fallback)",
    }

    if not stu_url:
        logger.warning(f"HWID {hwid}: missing HomeworkLink — cannot grade.")
        fallback["escalation_reason"] = "Missing HomeworkLink URL."
        return fallback

    if not ans_url:
        logger.warning(f"HWID {hwid}: missing AnswerKey — cannot grade.")
        fallback["escalation_reason"] = "Missing AnswerKey URL."
        return fallback

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not set — agent grading unavailable.")
        fallback["escalation_reason"] = "OPENAI_API_KEY missing."
        return fallback

    client = OpenAI(api_key=api_key)
    execute_tool, get_result = _make_executor(hw)

    # Convert TOOLS to OpenAI function schema format
    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            }
        }
        for tool in TOOLS
    ]

    user_message = (
        f"Please grade the following student homework submission.\n\n"
        f"HomeworkID: {hwid}\n"
        f"StudentName: {hw.get('StudentName', 'Unknown')}\n"
        f"SectionName: {hw.get('SectionName', 'Unknown')}\n"
        f"Submission URL: {stu_url}\n"
        f"Answer Key URL: {ans_url}\n\n"
        "Follow the grading process defined in your instructions: fetch both ZIPs, "
        "validate format, evaluate semantically, write personalized feedback, "
        "then call finalize_grade."
    )

    openai_messages = [  # type: ignore[var-annotated]
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    logger.info(f"🤖 Agent grading started for HWID {hwid}")

    for turn in range(MAX_AGENT_TURNS):
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=openai_messages,  # type: ignore[arg-type]
                tools=openai_tools,  # type: ignore[arg-type]
                tool_choice="auto",
            )
        except Exception as e:
            logger.error(f"HWID {hwid}: OpenAI API error on turn {turn + 1}: {e}")
            break

        finish_reason = response.choices[0].finish_reason
        logger.info(f"🤖 Turn {turn + 1} | finish_reason={finish_reason}")

        assistant_message = response.choices[0].message

        # Build a serializable assistant dict for the history
        assistant_dict: Dict[str, Any] = {
            "role": "assistant",
            "content": assistant_message.content,
        }
        if assistant_message.tool_calls:
            assistant_dict["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,  # type: ignore[union-attr]
                        "arguments": tc.function.arguments,  # type: ignore[union-attr]
                    },
                }
                for tc in assistant_message.tool_calls
            ]
        openai_messages.append(assistant_dict)

        if finish_reason == "stop":
            break

        if finish_reason != "tool_calls":
            logger.warning(
                f"HWID {hwid}: unexpected finish_reason={finish_reason} — stopping."
            )
            break

        # Execute every tool call in this turn; append each result individually
        finalized = False
        for tc in (assistant_message.tool_calls or []):
            tool_name = tc.function.name  # type: ignore[union-attr]
            tool_input = json.loads(tc.function.arguments)  # type: ignore[union-attr]

            logger.info(f"🔧 Tool: {tool_name} | input={json.dumps(tool_input)[:300]}")
            tool_output = execute_tool(tool_name, tool_input)
            logger.info(f"🔧 Result: {tool_output[:300]}")

            openai_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_output,
            })

            if tool_name == "finalize_grade":
                finalized = True

        if finalized:
            logger.info(f"✅ finalize_grade called — exiting agent loop for HWID {hwid}")
            break

    result = get_result()
    if result is None:
        logger.error(
            f"HWID {hwid}: agent finished {MAX_AGENT_TURNS} turns without calling "
            "finalize_grade — returning fallback."
        )
        return fallback

    logger.info(f"✅ Agent grade for HWID {hwid}: {result['grade']}")
    return result
