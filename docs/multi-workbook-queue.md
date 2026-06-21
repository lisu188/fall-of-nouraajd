# Multiple planning workbooks

The controller queue can span more than one XLSX workbook under `planning/`.
Use `scripts/workbook_queue.py` as the controller-facing entry point. The
single-workbook `scripts/issue_queue.py` remains supported for focused repair,
backward compatibility, and explicit `--workbook` operations.

## Queue discovery

With no explicit workbook option, the aggregate CLI scans `planning/*.xlsx`.
A workbook is a writable queue only when it contains an `Issue Proposals`
sheet. Its queue schema is then validated against the same required and
workflow columns used by `scripts/issue_queue.py`.

Current queue-compatible workbooks are:

- `planning/fall_of_nouraajd_issue_proposals.xlsx`
- `planning/fall_of_nouraajd_creature_archetype_jira_plan.xlsx`
- `planning/fall_of_nouraajd_github_issues_implementation_workbook.xlsx`

The GitHub issues implementation workbook retains its original planning sheets
(`Dashboard`, `GitHub Issues`, `Implementation Briefs`, `Source Evidence`, and
`Validation & Close Log`) and adds a canonical `Issue Proposals` sheet. The
queue rows preserve the source issue number and source-backed implementation
notes while initializing workflow state as unclaimed `NOT_STARTED` work.

Inspect discovery before dispatching:

```bash
python3 scripts/workbook_queue.py workbooks
python3 scripts/workbook_queue.py validate
```

The JSON form is available with `workbooks --json`.

## Controller commands

Use the aggregate CLI for queue reads and state transitions:

```bash
python3 scripts/workbook_queue.py controller-id --plain
python3 scripts/workbook_queue.py shortlist \
  --seed "$CONTROLLER_ID-$(date -u +%Y%m%dT%H%M%SZ)" \
  --controller-id "$CONTROLLER_ID" \
  --include-rejected \
  --json
python3 scripts/workbook_queue.py claim --owner "$OWNER" --issue "$ISSUE_NAME"
python3 scripts/workbook_queue.py prompt \
  --issue "$ISSUE_NAME" --claim-id "$CLAIM_ID" --owner "$OWNER"
```

The aggregate shortlist applies status, dependency, priority, story grouping,
controller-capacity, stale-claim, and source-overlap rules across all compatible
workbooks. Payloads include the selected `Workbook`/`workbook` path.
Cross-workbook dependencies are resolved against the combined issue set.
Duplicate `Issue Name` values across workbooks are validation errors and block
mutation until the collision is resolved.

All other state commands (`heartbeat`, `complete`, `block`, `fail`, `cancel`,
`release`, and `reclaim-stale`) locate the unique source workbook from the issue
name before delegating the existing atomic XLSX update.

## Overrides

For a focused single-workbook operation, pass `--workbook <path>`. Repeating
`--workbook` selects an explicit set. Automation may also set
`GAME_ISSUE_QUEUE_FILES` to an OS-path-separator-delimited list. The existing
`GAME_ISSUE_QUEUE_FILE` variable remains supported as a single-workbook
fallback.

## Pull-request safety

Each queue-state pull request must modify exactly one queue workbook and no
source files. Validate the aggregate state and the selected workbook before
publication. Do not batch binary edits across workbooks in one PR. Worker
implementation branches must not edit any queue workbook.

The dedicated `workbook queues` GitHub Actions workflow runs aggregate queue
validation and focused regressions. Planning XLSX changes and the queue tooling
are classified as lightweight; they do not require native game builds solely
because they are spreadsheet/workflow changes.

## Validation

Run from the repository root:

```bash
python3 -m unittest tests.test_workbook_queue
python3 scripts/workbook_queue.py workbooks --json
python3 scripts/workbook_queue.py validate
python3 -m unittest tests.test_issue_queue
python3 -m unittest tests.test_ci_change_classifier
```
