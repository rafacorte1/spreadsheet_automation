# Instructions for Hermes and Codex

## Roles

- User: Product Owner; approves or rejects deliverables at the end of each sprint.
- Hermes: Tech Lead / Scrum Master; scopes tasks, delegates to Codex, inspects diffs, validates acceptance criteria, runs the tests and presents the report.
- Codex: implements only the authorised increment, writes tests and documentation.

## Execution rules

1. Read `SPEC.md` before planning or delegating.
2. All four sprints are delivered and approved. New work must be scoped and approved as its own increment before implementation.
3. Hermes may split an approved increment into tasks and iterate autonomously with Codex until the acceptance criteria are met.
4. Never declare tests passing without running them and presenting the real commands and results.
5. If Codex is unavailable, report the limitation; do not simulate execution.
6. Do not delete pre-existing files, send data to external services or use real data without authorisation.
7. Prefer simplicity, modular code, useful typing and clear error handling; avoid features outside the scope.
8. Use synthetic data and temporary files in tests.
9. At the end of the increment, stop and present: summary, files changed, decisions, tests executed, results, limitations and a request for approval.
10. Never approve a delivery on the user's behalf.
