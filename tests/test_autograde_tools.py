"""
Tests for autograde_tools.py — current approved behavior only.

Scope:
  - _map_score_to_grade          (pure — no mocking needed)
  - _grade_sql_structural        (pure — no mocking needed)
  - _grade_docx_screenshot_structure    (mocks _extract_docx_from_zip)
  - _grade_paragraph_presence_structure (mocks _extract_docx_from_zip)
  - build_final_comments_and_feedback   (pure — no mocking needed)

Out of scope:
  - Network / download_file
  - Database calls
  - autograde_homework / autograde_homework_hybrid end-to-end
  - Screenshot correctness (not in scope / reverted)

Run from project root:
  pytest tests/test_autograde_tools.py -v
"""

import pytest
from unittest.mock import patch

from autograde_tools import (
    _map_score_to_grade,
    _grade_sql_structural,
    _grade_docx_screenshot_structure,
    _grade_paragraph_presence_structure,
    build_final_comments_and_feedback,
)

# ============================================================
# SQL fixtures
# ============================================================

# Full-featured answer key: requires JOIN + GROUP BY + COUNT
SQL_FULL = """
SELECT c.CustomerID, c.Name, COUNT(o.OrderID) AS order_count
FROM Customers c
JOIN Orders o ON c.CustomerID = o.CustomerID
WHERE c.IsActive = 1
GROUP BY c.CustomerID, c.Name
"""

# Student matches answer key completely
SQL_STUDENT_FULL_MATCH = SQL_FULL

# Student has JOIN + GROUP BY but missing COUNT (triggers strict COUNT enforcement)
SQL_STUDENT_NO_COUNT = """
SELECT c.Name, o.Total
FROM Customers c
JOIN Orders o ON c.CustomerID = o.CustomerID
WHERE c.IsActive = 1
GROUP BY c.Name, o.Total
"""

# Answer key without COUNT: requires JOIN + GROUP BY + SUM + HAVING (4 ops)
SQL_ANS_AGGREGATE = """
SELECT c.Name, SUM(o.Total) AS total
FROM Customers c
JOIN Orders o ON c.CustomerID = o.CustomerID
GROUP BY c.Name
HAVING SUM(o.Total) > 100
"""

# Student for partial match: has JOIN + GROUP BY only (2 of 4 → score 0.5 → grade 4)
SQL_STUDENT_PARTIAL = """
SELECT c.Name
FROM Customers c
JOIN Orders o ON c.CustomerID = o.CustomerID
GROUP BY c.Name
"""

# Single simple query (used to build multi-query answer key scenarios)
SQL_SIMPLE = "SELECT Name FROM Customers"

# Patch path for DOCX tests
_PATCH = "autograde_tools._extract_docx_from_zip"


# ============================================================
# _map_score_to_grade
# ============================================================

class TestMapScoreToGrade:
    """Pure threshold mapping — no mocking."""

    def test_perfect_score_gives_grade_5(self):
        assert _map_score_to_grade(1.0) == 5

    def test_boundary_0_60_gives_grade_5(self):
        assert _map_score_to_grade(0.60) == 5

    def test_just_below_0_60_gives_grade_4(self):
        assert _map_score_to_grade(0.59) == 4

    def test_boundary_0_40_gives_grade_4(self):
        assert _map_score_to_grade(0.40) == 4

    def test_just_below_0_40_gives_grade_3(self):
        assert _map_score_to_grade(0.39) == 3

    def test_boundary_0_20_gives_grade_3(self):
        assert _map_score_to_grade(0.20) == 3

    def test_just_below_0_20_gives_grade_2(self):
        assert _map_score_to_grade(0.19) == 2

    def test_boundary_0_10_gives_grade_2(self):
        assert _map_score_to_grade(0.10) == 2

    def test_just_below_0_10_gives_grade_1(self):
        assert _map_score_to_grade(0.09) == 1

    def test_zero_gives_grade_1(self):
        assert _map_score_to_grade(0.0) == 1


# ============================================================
# _grade_sql_structural
# ============================================================

class TestGradeSqlStructural:
    """Pure function — no mocking. All assertions derived from
    _extract_structural_fingerprint + _map_score_to_grade logic."""

    def test_happy_path_full_match_gives_grade_5(self):
        result = _grade_sql_structural(SQL_FULL, SQL_STUDENT_FULL_MATCH)
        assert result["grade"] == 5
        assert result["structural_valid"] is True
        assert result["escalate"] is False
        assert result["escalation_reason"] is None
        assert result["sql_missing_ops"] == []

    def test_missing_count_when_required_returns_score_zero_grade_1(self):
        # Answer key has COUNT; strict enforcement returns 0.0 immediately.
        result = _grade_sql_structural(SQL_FULL, SQL_STUDENT_NO_COUNT)
        assert result["score"] == 0.0
        assert result["grade"] == 1
        assert result["escalate"] is True
        assert "missing_count" in result["sql_missing_ops"]

    def test_partial_structural_match_gives_grade_4(self):
        # Answer: JOIN + GROUP BY + SUM + HAVING (4 required, no COUNT).
        # Student: JOIN + GROUP BY only → 2/4 = 0.50 → grade 4.
        result = _grade_sql_structural(SQL_ANS_AGGREGATE, SQL_STUDENT_PARTIAL)
        assert result["grade"] == 4
        assert result["structural_valid"] is True
        assert result["escalate"] is False
        # Both SUM and HAVING should be listed as missing
        assert "has_sum" in result["sql_missing_ops"]
        assert "has_having" in result["sql_missing_ops"]

    def test_no_detectable_queries_in_student_sql_gives_grade_1_escalate(self):
        result = _grade_sql_structural(SQL_FULL, "   \n\n   ")
        assert result["grade"] == 1
        assert result["structural_valid"] is False
        assert result["escalate"] is True
        assert "no detectable sql" in result["escalation_reason"].lower()

    def test_student_fewer_queries_than_answer_key_gives_grade_2_escalate(self):
        # Answer key: 2 queries. Student: 1 query.
        two_query_key = SQL_FULL + ";\n" + SQL_SIMPLE
        result = _grade_sql_structural(two_query_key, SQL_SIMPLE)
        assert result["grade"] == 2
        assert result["escalate"] is True
        assert "1 of 2" in result["escalation_reason"]

    def test_empty_answer_key_gives_grade_1_escalate(self):
        result = _grade_sql_structural("", SQL_FULL)
        assert result["grade"] == 1
        assert result["structural_valid"] is False
        assert result["escalate"] is True

    def test_return_shape_has_all_required_keys(self):
        result = _grade_sql_structural(SQL_FULL, SQL_STUDENT_FULL_MATCH)
        for key in ("grade", "structural_valid", "escalate", "escalation_reason",
                    "score", "sql_missing_ops", "sql_partial_ops"):
            assert key in result, f"Missing key: {key}"

    def test_escalate_is_true_when_grade_le_2(self):
        # grade <= 2 must escalate per the structural rule
        result = _grade_sql_structural(SQL_FULL, SQL_STUDENT_NO_COUNT)
        assert result["grade"] <= 2
        assert result["escalate"] is True

    def test_escalate_is_false_when_grade_ge_3(self):
        result = _grade_sql_structural(SQL_ANS_AGGREGATE, SQL_STUDENT_PARTIAL)
        assert result["grade"] >= 3
        assert result["escalate"] is False


# ============================================================
# _grade_docx_screenshot_structure (screenshot-count-only)
# ============================================================

class TestGradeDocxScreenshotStructure:
    """Mocks _extract_docx_from_zip to control (text, img_count)."""

    def _call(self, text: str, img_count: int):
        with patch(_PATCH, return_value=(text, img_count)):
            return _grade_docx_screenshot_structure("fake.zip")

    def test_five_screenshots_gives_grade_5(self):
        result = self._call("text", 5)
        assert result["grade"] == 5
        assert result["escalate"] is False
        assert result["escalation_reason"] is None

    def test_seven_screenshots_gives_grade_5(self):
        assert self._call("text", 7)["grade"] == 5

    def test_three_screenshots_gives_grade_4(self):
        result = self._call("text", 3)
        assert result["grade"] == 4
        assert result["escalate"] is False

    def test_four_screenshots_gives_grade_4(self):
        assert self._call("text", 4)["grade"] == 4

    def test_one_screenshot_gives_grade_3(self):
        result = self._call("text", 1)
        assert result["grade"] == 3
        assert result["escalate"] is False

    def test_two_screenshots_gives_grade_3(self):
        assert self._call("text", 2)["grade"] == 3

    def test_text_only_no_screenshots_gives_grade_2_no_escalate(self):
        result = self._call("Some paragraph text here.", 0)
        assert result["grade"] == 2
        assert result["structural_valid"] is True
        assert result["escalate"] is False
        assert result["screenshot_count"] == 0

    def test_empty_submission_gives_grade_1_escalate(self):
        result = self._call("", 0)
        assert result["grade"] == 1
        assert result["structural_valid"] is False
        assert result["escalate"] is True
        assert result["escalation_reason"] is not None

    def test_assignment_type_is_always_docx(self):
        assert self._call("text", 3)["assignment_type"] == "docx"

    def test_screenshot_count_reflects_img_count(self):
        assert self._call("text", 6)["screenshot_count"] == 6

    def test_return_shape_has_all_required_keys(self):
        result = self._call("text", 3)
        for key in ("grade", "assignment_type", "structural_valid",
                    "screenshot_count", "paragraph_count",
                    "escalate", "escalation_reason"):
            assert key in result, f"Missing key: {key}"


# ============================================================
# _grade_paragraph_presence_structure
# ============================================================

class TestGradeParagraphPresenceStructure:
    """Mocks _extract_docx_from_zip to control paragraph text."""

    def _paragraphs(self, n: int) -> str:
        """Return text with exactly n non-empty lines."""
        return "\n".join(f"Paragraph {i + 1} content." for i in range(n))

    def _call(self, n_paragraphs: int, img_count: int = 0):
        text = self._paragraphs(n_paragraphs)
        with patch(_PATCH, return_value=(text, img_count)):
            return _grade_paragraph_presence_structure("fake.zip")

    def test_four_paragraphs_gives_grade_5(self):
        result = self._call(4)
        assert result["grade"] == 5
        assert result["escalate"] is False

    def test_more_than_four_paragraphs_gives_grade_5(self):
        assert self._call(6)["grade"] == 5

    def test_three_paragraphs_gives_grade_4(self):
        result = self._call(3)
        assert result["grade"] == 4
        assert result["escalate"] is False

    def test_two_paragraphs_gives_grade_3(self):
        result = self._call(2)
        assert result["grade"] == 3
        assert result["escalate"] is False

    def test_one_paragraph_gives_grade_2(self):
        result = self._call(1)
        assert result["grade"] == 2
        assert result["escalate"] is False

    def test_no_paragraphs_gives_grade_1_escalate(self):
        result = self._call(0)
        assert result["grade"] == 1
        assert result["escalate"] is True
        assert result["escalation_reason"] is not None

    def test_assignment_type_is_paragraph(self):
        assert self._call(3)["assignment_type"] == "paragraph"

    def test_return_shape_has_all_required_keys(self):
        result = self._call(3)
        for key in ("grade", "assignment_type", "structural_valid",
                    "screenshot_count", "paragraph_count",
                    "escalate", "escalation_reason"):
            assert key in result, f"Missing key: {key}"


# ============================================================
# build_final_comments_and_feedback — v8 invariant
# ============================================================

class TestBuildFinalCommentsAndFeedback:
    """
    v8 rule: comments and feedback depend ONLY on final_grade + assignment_type.
    Grading source (Python vs AI) must NEVER affect output.
    """

    # --- SQL ---

    def test_sql_grade_5_contains_excellent_marker(self):
        c, _ = build_final_comments_and_feedback(final_grade=5, assignment_type="sql")
        assert "Excellent" in c or "🌟" in c

    def test_sql_grade_4_includes_missing_op_in_comments(self):
        c, _ = build_final_comments_and_feedback(
            final_grade=4, assignment_type="sql",
            sql_missing_ops=["has_group_by"],
        )
        assert "has_group_by" in c

    def test_sql_grade_3_includes_missing_op_in_comments(self):
        c, _ = build_final_comments_and_feedback(
            final_grade=3, assignment_type="sql",
            sql_missing_ops=["has_join"],
        )
        assert "has_join" in c

    def test_sql_grade_4_does_not_show_partial_ops_when_none_given(self):
        c, _ = build_final_comments_and_feedback(final_grade=4, assignment_type="sql")
        assert "Partially implemented" not in c

    # --- DOCX ---

    def test_docx_grade_5_contains_screenshot_marker(self):
        c, _ = build_final_comments_and_feedback(
            final_grade=5, assignment_type="docx", screenshot_count=6,
        )
        assert "📸" in c or "screenshot" in c.lower()

    def test_docx_grade_3_contains_improvement_prompt(self):
        c, _ = build_final_comments_and_feedback(
            final_grade=3, assignment_type="docx", screenshot_count=1,
        )
        assert "💡" in c

    def test_docx_grade_1_contains_incomplete_marker(self):
        c, _ = build_final_comments_and_feedback(final_grade=1, assignment_type="docx")
        assert "⚠️" in c or "incomplete" in c.lower() or "missing" in c.lower()

    # --- Paragraph ---

    def test_paragraph_grade_5_shows_paragraph_count(self):
        c, _ = build_final_comments_and_feedback(
            final_grade=5, assignment_type="paragraph", paragraph_count=4,
        )
        assert "4" in c

    def test_paragraph_grade_1_shows_zero_count(self):
        c, _ = build_final_comments_and_feedback(
            final_grade=1, assignment_type="paragraph", paragraph_count=0,
        )
        assert "0" in c

    # --- missing_required_files prefix ---

    def test_missing_files_prefix_shown_at_grade_1(self):
        c, _ = build_final_comments_and_feedback(
            final_grade=1, assignment_type="docx",
            missing_required_files=["submission.docx"],
        )
        assert "Missing required file" in c
        assert "submission.docx" in c

    def test_missing_files_prefix_not_shown_at_grade_2(self):
        # Prefix only applies at grade 1
        c, _ = build_final_comments_and_feedback(
            final_grade=2, assignment_type="docx",
            missing_required_files=["submission.docx"],
        )
        assert "Missing required file" not in c

    # --- v8 invariant: grading source does not affect output ---

    def test_same_grade_and_type_always_produce_identical_sql_output(self):
        """Calling twice with identical args must return identical output."""
        result_a = build_final_comments_and_feedback(final_grade=4, assignment_type="sql")
        result_b = build_final_comments_and_feedback(final_grade=4, assignment_type="sql")
        assert result_a == result_b

    def test_same_grade_and_type_always_produce_identical_docx_output(self):
        result_a = build_final_comments_and_feedback(final_grade=3, assignment_type="docx")
        result_b = build_final_comments_and_feedback(final_grade=3, assignment_type="docx")
        assert result_a == result_b

    def test_different_assignment_types_produce_different_comments_at_same_grade(self):
        """SQL grade 3 ≠ DOCX grade 3 — type determines content."""
        sql_c, _ = build_final_comments_and_feedback(final_grade=3, assignment_type="sql")
        doc_c, _ = build_final_comments_and_feedback(final_grade=3, assignment_type="docx")
        assert sql_c != doc_c

    def test_different_grades_produce_different_comments_for_same_type(self):
        c3, _ = build_final_comments_and_feedback(final_grade=3, assignment_type="sql")
        c5, _ = build_final_comments_and_feedback(final_grade=5, assignment_type="sql")
        assert c3 != c5

    def test_feedback_html_is_not_empty_for_any_grade_and_type(self):
        for grade in (1, 2, 3, 4, 5):
            for atype in ("sql", "docx", "paragraph"):
                _, f = build_final_comments_and_feedback(
                    final_grade=grade, assignment_type=atype
                )
                assert f, f"Empty feedback for grade={grade} type={atype}"


# ============================================================
# SQL pattern coverage — fingerprint-tracked and untracked ops
# ============================================================

# Fixture design notes:
#   "match" tests: student SQL == answer SQL → score 1.0 → grade 5
#   "missing" tests: answer has (feature + GROUP BY); student has GROUP BY only
#     → score 0.5 → grade 4 (except CTE which also triggers has_subquery → score 0.33 → grade 3)
#     This ensures score > 0.0 so the missing key is actually recorded in sql_missing_ops.
#     (When score == 0.0, _grade_sql_structural leaves sql_missing_ops empty by design.)

_FINGERPRINT_FIXTURES = [
    # (answer_sql, student_sql_for_missing_case, feature_key, expected_grade_when_missing)
    (
        "SELECT AVG(col) FROM t GROUP BY x",
        "SELECT col FROM t GROUP BY x",
        "has_avg", 4,
    ),
    (
        "SELECT MIN(col) FROM t GROUP BY x",
        "SELECT col FROM t GROUP BY x",
        "has_min", 4,
    ),
    (
        "SELECT MAX(col) FROM t GROUP BY x",
        "SELECT col FROM t GROUP BY x",
        "has_max", 4,
    ),
    (
        "SELECT DISTINCT col FROM t GROUP BY x",
        "SELECT col FROM t GROUP BY x",
        "has_distinct", 4,
    ),
    # CTE answer also triggers has_subquery (the `(SELECT …)` inside WITH),
    # so total_required=3, student satisfies 1 (GROUP BY) → grade 3.
    (
        "WITH cte AS (SELECT 1) SELECT * FROM cte GROUP BY 1",
        "SELECT 1 GROUP BY 1",
        "has_cte", 3,
    ),
    (
        "SELECT * FROM (SELECT id FROM t) sub GROUP BY sub.id",
        "SELECT id FROM t GROUP BY id",
        "has_subquery", 4,
    ),
]


class TestSqlPatternCoverage:
    """
    Explicit coverage for every fingerprint-tracked SQL pattern not already
    covered in TestGradeSqlStructural, plus a confirmation that SQL_OPS-only
    patterns (ORDER BY, CASE, DML, DDL, implicit join) have no scoring effect
    because _extract_structural_fingerprint does not track them.
    """

    @pytest.mark.parametrize(
        "ans_sql, _student, feature_key, _expected_grade",
        _FINGERPRINT_FIXTURES,
        ids=[f[2] for f in _FINGERPRINT_FIXTURES],
    )
    def test_pattern_present_in_student_gives_grade_5(
        self, ans_sql, _student, feature_key, _expected_grade
    ):
        # Student == answer → perfect structural match → grade 5, nothing missing.
        result = _grade_sql_structural(ans_sql, ans_sql)
        assert result["grade"] == 5
        assert feature_key not in result["sql_missing_ops"]
        assert result["escalate"] is False

    @pytest.mark.parametrize(
        "ans_sql, student_sql, feature_key, expected_grade",
        _FINGERPRINT_FIXTURES,
        ids=[f[2] for f in _FINGERPRINT_FIXTURES],
    )
    def test_pattern_missing_in_student_listed_in_missing_ops(
        self, ans_sql, student_sql, feature_key, expected_grade
    ):
        # Student satisfies the non-feature op (GROUP BY) but not the feature itself,
        # so score > 0.0 and the feature key is recorded in sql_missing_ops.
        result = _grade_sql_structural(ans_sql, student_sql)
        assert result["grade"] == expected_grade
        assert feature_key in result["sql_missing_ops"]

    @pytest.mark.parametrize("untracked_sql", [
        "ORDER BY name",
        "CASE WHEN x > 1 THEN 'y' ELSE 'n' END",
        "CREATE TABLE t (id INT)",
        "INSERT INTO t VALUES (1)",
        "UPDATE t SET x = 1",
        "DELETE FROM t WHERE id = 1",
        "ALTER TABLE t ADD col INT",
        "SELECT * FROM t1, t2 WHERE t1.id = t2.id",  # implicit join
    ])
    def test_sql_ops_only_patterns_have_no_structural_scoring_effect(
        self, untracked_sql
    ):
        # These patterns live in SQL_OPS but are absent from _extract_structural_fingerprint.
        # total_required == 0 for any answer key that uses only these patterns,
        # so _compare_structure returns score 1.0 regardless of the student query.
        result = _grade_sql_structural(untracked_sql, "SELECT 1")
        assert result["grade"] == 5
        assert result["escalate"] is False
        assert result["sql_missing_ops"] == []
