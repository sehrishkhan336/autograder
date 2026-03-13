# Claude Code Repository Rules

## Working Rules
- Do not make changes unless explicitly asked.
- Make only one scoped change at a time.
- Explain what you are changing before making the change.
- Do not refactor unrelated code.
- Do not change production behavior unless the requested task requires it.
- Preserve existing logic unless the task is specifically to modify it.
- Keep changes minimal and easy to review.

## Safety Rules
- Do not expose internal grading logic in student-facing comments or feedback.
- Do not expose internal requirements, validator rules, scoring formulas, or system logic in student emails.
- Student-facing messages should only describe what is missing and how to improve.

## Workflow Rules
- Read the relevant file(s) first before editing.
- Show the exact files changed.
- Summarize the change after editing.
- Stop after completing the requested change.
- If something is unclear, state the assumption instead of making broad changes.

## For This Project
- AI is the primary grading authority for Version 2.
- Python is a support/validation layer for structure and format checks.
- Do not implement platform or backend integration changes unless explicitly requested.
- Focus only on the grading module inside the Colaberry app.