# Multi-workbook queue controller addendum

This addendum overrides only the single-workbook selection and command examples
in `prompts/codex-queue-controller.md` and `docs/codex-agent-queue.md`. All
other controller safety, branch, validation, worker, PR, recovery, and merge
rules remain in force.

1. Read `docs/multi-workbook-queue.md` during startup.
2. Use `python3 scripts/workbook_queue.py` for discovery, validation, shortlist,
   claim, prompt, heartbeat, terminal state, release, and reclaim operations.
3. Treat every queue-compatible `planning/*.xlsx` workbook as part of one
   aggregate implementation queue. Do not assume the original issue-proposals
   workbook is the only source.
4. Run `workbooks --json` and `validate` before dispatch. Report skipped
   non-queue workbooks and their exact schema reason; never mutate them through
   guessed mappings.
5. Select from the aggregate highest eligible priority tier. Resolve
   dependencies and controller capacity globally. Record the selected workbook
   path in live status and worker handoff.
6. Publish each claim, heartbeat, priority/dependency adjustment, reclaim, or
   terminal update as a PR that modifies exactly one queue workbook. Never edit
   two XLSX queues concurrently in the same branch or PR.
7. Worker implementation branches must not modify any file reported as a
   queue-compatible workbook by `workbooks --json`.
8. A duplicate issue name across workbooks or aggregate validation failure is a
   dispatch blocker. Fix the verified queue defect through a separate,
   serialized workbook PR; do not select by workbook order to bypass it.
