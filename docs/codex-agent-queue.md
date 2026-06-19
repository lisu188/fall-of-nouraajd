# Local Codex agent queue

This workflow lets one controller Codex process coordinate local worker subagents while the committed XLSX workbook
remains the canonical task queue. The controller owns Git worktrees, queue-state pull requests, implementation pull
requests, and terminal workbook updates. Worker subagents implement code in isolated branches and must never edit the
workbook.

## Files

- `planning/fall_of_nouraajd_issue_proposals.xlsx` — canonical queue and human-readable backlog.
- `scripts/issue_queue.py` — atomic claim/progress/completion CLI.
- `prompts/codex-queue-controller.md` — controller-agent operating prompt.
- `tests/test_issue_queue.py` — focused queue and concurrency regressions.

The queue CLI and its focused tests use only the Python standard library. The XLSX package is edited at the OOXML worksheet level so unrelated charts, styles, tables, validation extensions, and package parts are preserved.

## Safety model

The queue uses two different mechanisms:

1. A sidecar `*.xlsx.lock` file is locked by the operating system for every workbook mutation. Only one process can perform a claim or update at a time.
2. The changed workbook is first written to a temporary XLSX in the same directory and then moved over the canonical file with `os.replace()`. A process crash before replacement leaves the original workbook intact.

Each active row has both an `Owner` and a random `Claim ID`. Heartbeat, completion, block, failure, cancellation, and release operations require both values. A subagent cannot update a task merely by knowing its issue title.

The queue lock prevents duplicate task claims. It does **not** prevent two subagents from editing the same source file.
By default `claim` skips tasks whose exact `Target Files / Modules` overlap an existing `IN_PROGRESS` row. The
controller must still inspect scopes and serialize work when shared headers, bindings, tests, CMake, map scripts,
dialog/config files, serialization, generated resources, or shared runtime systems are coupled.

## Setup

From repository root:

```bash
python3 scripts/issue_queue.py validate
python3 -m unittest tests.test_issue_queue
```

The default workbook is `planning/fall_of_nouraajd_issue_proposals.xlsx`. Override it with either:

```bash
export GAME_ISSUE_QUEUE_FILE=/absolute/path/to/issues.xlsx
```

or `--workbook <path>` on each command.

## Controller dispatch loop

Validate first:

```bash
python3 scripts/issue_queue.py validate
```

The queue CLI `claim` command is deterministic: it picks the first eligible row by priority and workbook order. The
controller workflow requires explicit random selection instead. Before each claim, fetch latest `origin/main`, read the
merged workbook, and calculate the complete eligible set by excluding:

- rows whose status is not `NOT_STARTED`;
- rows with unfinished dependencies;
- direct target-file overlaps with active work;
- active-scope conflicts;
- indirect conflicts through shared headers, bindings, tests, CMake, map scripts, dialog/config files, serialization,
  generated resources, or shared runtime systems.

Keep only the highest currently available priority tier. Group remaining candidates by `(Epic #, Story #)`, randomly
select one story with equal probability, then randomly select one eligible substory inside it. Never default to workbook
order and never randomize ineligible rows.

Before dispatch/refill decisions, assign a read-only project manager role when subagent capacity permits. The project
manager reviews the merged workbook, active work, stale claims, blockers, dependency chains, validation cost, RAM/disk
limits, and open PR state, then reports:

- the highest available priority tier and candidate `(Epic #, Story #)` groups;
- issues likely to unblock other work;
- stale, blocked, failed, or repeatedly deferred rows needing controller attention;
- scope, validation, resource, and sequencing risks;
- source-backed recommendations for priority changes, issue splits, deferrals, or blocker publications.

The project manager is advisory. It must not claim issues, edit files, touch the workbook, start validation, or override
the dependency, conflict, highest-priority-tier, randomized story/substory, RAM, disk, or PR requirements. Any priority,
dependency, status, or scope change must be approved by the user or controller and merged through a serialized
workbook-only pull request before it affects dispatch.

After selecting an exact issue, claim that row:

```bash
python3 scripts/issue_queue.py claim \
  --owner controller/subagent-1 \
  --lease-minutes 1440 \
  --issue "$ISSUE_NAME"
```

The claim branch and pull request must be workbook-only and must merge before implementation starts. After the claim PR
actually merges into `main`, create the implementation worktree from the updated `origin/main`, generate the worker
prompt, and assign exactly one worker to that implementation branch.

The CLI considers a row mechanically eligible only when:

- status is `NOT_STARTED`;
- every issue in `Dependencies` is `DONE`;
- optional priority/epic/component filters match;
- target files do not overlap currently active rows, unless `--allow-file-overlap` is explicitly supplied.

To claim an exact row:

```bash
python3 scripts/issue_queue.py claim \
  --owner controller/subagent-1 \
  --issue '[EPIC_01][STORY_01][SUBSTORY_01]Add explicit fight outcome model'
```

Generate the exact worker prompt after claiming:

```bash
python3 scripts/issue_queue.py prompt \
  --issue "$ISSUE_NAME" \
  --claim-id "$CLAIM_ID" \
  --owner controller/subagent-1
```

Alternatively use `claim --format prompt`.

## Live worker status

Keep at least four live subagents attached to the controller whenever the subagent interface is available. Keep four
implementation issues active whenever four safe, eligible, non-conflicting issues exist, and make that active
implementation count RAM- and disk-aware. Before dispatching or refilling implementation workers, inspect current
available RAM, swap pressure, free disk, accumulated run/worktrees, prunable worktree metadata, and running heavy
build/test/coverage/Xvfb/MCP jobs. Set the live implementation worker budget to the smaller of four and the number of
workers the machine can support without memory or disk pressure. If the controller cannot keep four issue workers
active, report the concrete eligibility, conflict, status, RAM, disk, cleanup, or repository-safety blocker.

Standby subagents may help with lightweight status polling, eligibility summaries, or review preparation only when fewer
than four implementation issues can safely run. They must not claim issues, edit files, touch the workbook, start builds,
run tests, or launch coverage/Xvfb/MCP validation.

When four implementation workers are not safe, prefer assigning one standby subagent as the project manager so the next
refill decision has a current prioritization brief. When four safe implementation issues and enough resources exist, the
project manager should run as extra read-only capacity rather than displacing an implementation worker.

Poll every active worker through the available subagent/task interface. If direct polling is unavailable, require
structured status updates from the worker.

After every controller loop iteration, cleanup audit, claim or pull-request status check, and before dispatching new
work, print a live status table containing at least:

- worker owner;
- issue key;
- current phase;
- progress estimate;
- last reported action;
- changed files if known;
- current validation command if running;
- branch name;
- pull request number or pending PR state;
- current RAM and disk state;
- cleanup state, including prunable worktree metadata and accumulated run/worktree size when known;
- project-manager prioritization brief state or the reason no project-manager subagent is available;
- blockers;
- next controller action.

Do not rely on workbook fields for live status. The workbook records durable queue state; live worker state comes from
subagent polling or structured worker reports.

Run the read-only resource audit before every dispatch/refill decision, before heavy validation, after each controller
loop, and after merged-checkpoint cleanup:

```bash
python3 scripts/controller_resource_audit.py --json
```

The audit reports disk usage, active and prunable worktree registrations, and matching controller run/worktrees such as
`/tmp/nouraajd-*` and `/tmp/fall-of-nouraajd-codex`. It is report-only by default. Treat audit errors as blockers to new
heavy work, and treat warnings about prunable worktree metadata or large accumulated run/worktrees as cleanup prompts
before refilling worker slots.

## Subagent progress protocol

A worker should report meaningful milestones to the controller after source inspection, root-cause analysis,
implementation, focused validation, and full validation. Workers must not update the workbook directly during queue
controller runs.

When the controller needs to persist a heartbeat, it does so from a fresh workbook-only branch:

```bash
python3 scripts/issue_queue.py heartbeat \
  --issue "$ISSUE_NAME" \
  --claim-id "$CLAIM_ID" \
  --owner controller/subagent-1 \
  --progress 20 \
  --note 'Root cause verified in CFightHandler.cpp and CCreature.cpp'
```

Every heartbeat extends the lease. Recommended checkpoints are 5%, 20%, 70%, and 90%.

Complete only after the implementation pull request has actually merged and validation results have been reviewed:

```bash
cat >/tmp/task-summary.txt <<'EOF'
Implemented the detailed fight result contract while preserving the bool compatibility API.
EOF

cat >/tmp/task-validation.txt <<'EOF'
cmake --build cmake-build-release --target _game for_unit_tests performance_guard_tests -j1: PASS
ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests: PASS
ctest --test-dir cmake-build-release --output-on-failure --verbose -L performance: PASS
python3 test.py: PASS
EOF

python3 scripts/issue_queue.py complete \
  --issue "$ISSUE_NAME" \
  --claim-id "$CLAIM_ID" \
  --owner controller/subagent-1 \
  --summary-file /tmp/task-summary.txt \
  --validation-file /tmp/task-validation.txt
```

`DONE` requires a result summary, validation results, `Progress %=100`, and a completion timestamp. Do not mark `DONE`
while implementation auto-merge is merely queued.

## Block, fail, cancel, and release

Verified source or environment blocker:

```bash
python3 scripts/issue_queue.py block \
  --issue "$ISSUE_NAME" \
  --claim-id "$CLAIM_ID" \
  --owner controller/subagent-1 \
  --note 'Referenced runtime object cannot be confirmed from source'
```

Implementation attempt failed:

```bash
python3 scripts/issue_queue.py fail ... --note 'Focused regression still fails: <exact output>'
```

Intentional cancellation:

```bash
python3 scripts/issue_queue.py cancel ... --note 'Controller cancelled due to overlapping refactor'
```

Return an owned task to the eligible queue:

```bash
python3 scripts/issue_queue.py release ... --note 'Returned before editing'
```

`BLOCKED`, `FAILED`, and `CANCELLED` rows are not selected automatically.

## Crash recovery

An `IN_PROGRESS` row has a `Lease Until UTC`. The controller can reclaim expired work:

```bash
python3 scripts/issue_queue.py reclaim-stale --dry-run --older-than-minutes 30
python3 scripts/issue_queue.py reclaim-stale --older-than-minutes 30
```

The dry run lists stale rows without modifying the workbook. Inspect the worker worktree, branch, pull request, and any
recoverable changes before running the mutating command. Run the mutating command only from a fresh workbook-only branch
and publish it through the same serialized queue-state PR process as claims and terminal statuses. Reclaimed rows are
not eligible for dispatch until that reclaim PR actually merges. The mutating command only reclaims rows whose lease is
already expired and whose last update is at least the specified age. Reclaimed rows return to `NOT_STARTED`, retain the
incremented `Attempt`, and receive an audit note describing the previous owner and claim.

`validate` warns about expired `IN_PROGRESS` leases without failing the workbook, and `list --status IN_PROGRESS --json`
includes derived lease-expiration fields for read-only controller status checks.

## Inspection commands

```bash
python3 scripts/issue_queue.py next
python3 scripts/issue_queue.py list --status IN_PROGRESS
python3 scripts/issue_queue.py list --status BLOCKED --json
python3 scripts/issue_queue.py show --issue "$ISSUE_NAME"
```

## Operating constraints

- Do not keep the XLSX open in desktop Excel/LibreOffice while agents are mutating it, especially on Windows; those programs may prevent atomic replacement.
- Do not edit `Status`, `Owner`, `Claim ID`, timestamps, lease, or progress manually while the controller is active.
- Keep a single controller responsible for dispatch and source-file overlap decisions.
- A worker must inspect relevant project files and verify repository-specific details against raw GitHub source before editing.
- A worker must make the smallest safe change and preserve public identifiers unless they are verified broken.
- Queue completion records validation; it does not prove the code has been integrated into another subagent's uncommitted work.
- Worker implementation branches must not modify `planning/fall_of_nouraajd_issue_proposals.xlsx`.
- Serialize workbook claim, heartbeat, and terminal-status pull requests; do not keep multiple binary workbook PRs open for merge.
- To spare RAM, queue-controller workers must use serial local builds such as `-j1` unless the user explicitly allows more parallelism.
- Multiple heavy build, test, coverage, Xvfb, or MCP validation jobs may run concurrently only inside the current
  RAM-safe heavy-job budget. If all heavy jobs are explicitly serial, such as `-j1` or equivalent, and RAM has headroom
  with no swap pressure, that budget can be at least four concurrent heavy jobs.
- Keep at least four live subagents and four active implementation issues whenever four issues are safe and eligible,
  using standby roles only when fewer than four implementation workers are safe.
- Recalculate the RAM-safe implementation worker and heavy-job budgets before each dispatch/refill and before starting
  heavy validation; fewer than four active implementation workers or heavy jobs can still be the correct budget.
- If RAM-safety limits or missing worker status prevent safe dispatch, stop filling worker slots until the blocker clears.
- If disk-safety limits, prunable worktree metadata, or accumulated run/worktree usage prevent safe dispatch, stop
  filling worker slots until the blocker is reported or safely cleaned.
- Remove only completed clean worktrees. Use `git worktree prune` only for prunable metadata after reviewing that the
  corresponding worktree directories no longer exist. Do not delete branches unless explicitly asked.
