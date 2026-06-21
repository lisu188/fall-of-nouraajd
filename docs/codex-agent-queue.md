# Local Codex agent queue

This workflow lets one or more controller Codex processes coordinate local worker subagents while the committed XLSX
workbook remains the canonical task queue. Controller instances own Git worktrees, queue-state pull requests,
implementation pull requests, and terminal workbook updates. Worker subagents implement code in isolated branches and
must never edit the workbook. Each controller instance must use a unique controller ID in its worker owner names so
concurrent controllers can be distinguished.

## Files

- `planning/fall_of_nouraajd_issue_proposals.xlsx` — canonical queue and human-readable backlog.
- `planning/workflow_observations/` — immutable workflow-observation records and resolution receipts; not a task queue.
- `scripts/issue_queue.py` — atomic claim/progress/completion CLI.
- `scripts/pr_review_audit.py` — read-only stale/open PR classification helper for merge, cleanup, and dispatch review.
- `scripts/workflow_observations.py` — read-only/append-only workflow-observation ledger CLI.
- `prompts/codex-queue-controller.md` — controller-agent operating prompt.
- `tests/test_issue_queue.py` — focused queue and concurrency regressions.

The queue CLI and its focused tests use only the Python standard library. The XLSX package is edited at the OOXML worksheet level so unrelated charts, styles, tables, validation extensions, and package parts are preserved.

## Safety model

The queue uses two different mechanisms:

1. A sidecar `*.xlsx.lock` file is locked by the operating system for every workbook mutation. Only one process can perform a claim or update at a time.
2. The changed workbook is first written to a temporary XLSX in the same directory and then moved over the canonical file with `os.replace()`. A process crash before replacement leaves the original workbook intact.

Each active row has both an `Owner` and a random `Claim ID`. Heartbeat, completion, block, failure, cancellation, and release operations require both values. A subagent cannot update a task merely by knowing its issue title.

The queue lock prevents duplicate task claims. It does **not** prevent two subagents from editing the same source file.
Exact `Target Files / Modules` overlap, open implementation PRs, and shared source areas are advisory coordination
evidence, not automatic claim blockers. The controller must inspect these signals and use them to shape worker prompts,
review order, expected rebase/merge risk, and validation focus, but a controller should not leave a worker slot empty
solely because status-and-dependency eligible work overlaps active source scope.

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

Generate a controller identity once at startup and reuse it for every owner string emitted by that controller:

```bash
CONTROLLER_ID="$(python3 scripts/issue_queue.py controller-id --plain)"
OWNER_PREFIX="controller/${CONTROLLER_ID}"
OWNER="${OWNER_PREFIX}/subagent-1"
python3 scripts/issue_queue.py controller-id --controller-id "$CONTROLLER_ID"
```

Owner names must include the controller ID, for example `controller/ctrl-host-1234-abcd1234/subagent-1`. Do not use
generic owners such as `controller/subagent-1`; multiple controllers may be running at the same time.

The queue CLI `claim` command is deterministic: it picks the first eligible row by priority and workbook order. The
controller workflow requires explicit random selection instead. Before each claim, fetch latest `origin/main`, read the
merged workbook, and generate a read-only mechanical shortlist:

```bash
python3 scripts/issue_queue.py shortlist \
  --seed "${CONTROLLER_ID}-$(date -u +%Y%m%dT%H%M%SZ)" \
  --controller-id "$CONTROLLER_ID" \
  --include-rejected \
  --json
```

The shortlist command does not mutate the workbook. It filters queue status, dependencies, and optional CLI filters,
keeps only the highest currently eligible priority tier for `storyGroups`, and emits a seeded recommended
`selected.issue.issueName`. It also reports `activeClaims.total`, `activeClaims.unexpired`, `activeClaims.healthy`,
`activeClaims.stale`, `activeClaims.leaseExpired`, `activeClaims.suspect`, `activeClaims.reclaimable`,
`activeClaims.inactive`, `staleClaimCount`, `staleClaims`, `advisoryTargetFileOverlapCount`,
`advisoryTargetFileOverlaps`, and per-issue `activeFileOverlaps` so heartbeat-overdue claims, expired leases, recovery
rows, and exact target-file overlaps can inform dispatch decisions without becoming automatic blockers.
`activeClaims.unexpired` is retained as the healthy live-claim count: heartbeat not overdue and lease not expired. When
`--controller-id` is provided, it also reports `controllerCapacity`: the current controller's healthy owned issues,
suspect owned issues, reclaimable owned issues, recovery-required state, deficit to the four-issue controller target,
active limit, available slots, over-limit count, over-capacity flag, and fillable deficit from the current eligible set.
Treat that output as mechanical evidence for the controller and project-manager brief, not as
an automatic claim. The controller and PM must still inspect coordination advisories, including:

- rows whose status is not `NOT_STARTED`;
- rows with unfinished dependencies;
- active target-file overlaps;
- open implementation PRs in nearby source areas;
- indirect shared scope through headers, bindings, tests, CMake, map scripts, dialog/config files, serialization,
  generated resources, or shared runtime systems.

Keep only the highest currently available priority tier. Group remaining candidates by `(Epic #, Story #)`, randomly
select one story with equal probability, then randomly select one eligible substory inside it. Never default to workbook
order, never randomize status/dependency-ineligible rows, and never fall back to a lower priority tier merely to avoid
source overlap. After final review, claim the exact selected issue with `claim --issue`; the claim command revalidates
status and dependency eligibility under the workbook lock.

Before dispatch/refill decisions, assign a read-only project manager role when subagent capacity permits. The project
manager reviews the merged workbook, active work, stale claims, blockers, dependency chains, validation cost, resource
state, disk cleanup needs, and open PR state, then reports:

- the highest available priority tier and candidate `(Epic #, Story #)` groups;
- issues likely to unblock other work;
- stale, blocked, failed, or repeatedly deferred rows needing controller attention;
- scope-overlap, validation, resource, and sequencing risks;
- source-backed recommendations for priority changes, issue splits, deferrals, or blocker publications.

The project manager is advisory. It must not claim issues, edit files, touch the workbook, start validation, or override
the dependency, highest-priority-tier, randomized story/substory, resource, cleanup, or PR requirements. Any priority,
dependency, status, or scope change must be approved by the user or controller and merged through a serialized
workbook-only pull request before it affects dispatch.

Before cleanup, stale-PR closure, stale-branch cleanup, or merge decisions, run a read-only open-PR review audit against
a normalized snapshot that includes changed files, merge state, CI rollup, queue linkage, and any local recovery signals:

```bash
python3 scripts/pr_review_audit.py --input /tmp/pr-review-snapshot.json --format table
```

The audit emits an `actionCategory` such as `ready_to_merge`, `poll`, `failing_ci`, `needs_update_rebase`,
`human_review_required`, `obsolete_duplicate_close`, `branch_cleanup_candidate`, or `never_touch`, plus a separate
`prType` such as `workbook_only_queue_pr`, `implementation_pr_with_active_workbook_claim`, `workflow_pr`, or
`unknown_pr`. Treat the result as advisory evidence for the controller and project-manager brief. It does not close PRs,
delete branches, touch the workbook, or bypass failing checks. Human approval is required before closing obsolete or
duplicate PRs, deleting local or remote branches, reclaiming recoverable stale claims, touching dirty worktrees, or
merging any PR with missing classification signals.

Controller-owned implementation PRs classified as `failing_ci`, `needs_update_rebase`, `human_review_required`, or
`never_touch` require controller attention or explicit recovery assignment before the controller treats their issues as
resolved. They do not reintroduce source-overlap as a hard claim exclusion: keep the exact four owned implementation
slots whenever status-and-dependency eligible work exists and no concrete non-source blocker prevents dispatch, but do
not refill through unresolved heartbeat-overdue, lease-expired, suspect, or reclaimable rows.

## Workflow observations

Use `docs/codex-workflow-observations.md` for the durable workflow-observation ledger. Observations are immutable JSON
evidence files for workflow problems such as queue/lease faults, missing live worker status, stale state, PR or merge
failures, CI waste, prompt drift, resource or recovery failures, unsafe ambiguity, and repeated manual intervention.
They are not gameplay defects, routine progress updates, or implementation queue rows.

Each queue controller may publish controller-discovered workflow observations directly after evidence and secret review.
Workers, QA, and project-manager agents report observations to their controller. They do not publish ledger files.
Observation updates are append-only: add a new record under `planning/workflow_observations/records/` or a new
resolution receipt under `planning/workflow_observations/resolutions/`. Do not edit or delete existing records or
receipts. The controller reviews evidence for secrets and relevance, runs
`python3 scripts/workflow_observations.py validate`, and publishes observation-only PRs that add only
`planning/workflow_observations/records/<id>.json`. After a workflow fix merges and post-merge verification passes,
publish a separate resolution-only PR that adds only `planning/workflow_observations/resolutions/<id>.json`.

Observation-only and resolution-only PRs are not CI-exempt under the current repository policy. They do not need the
global XLSX serialization lane because each record or receipt is a unique immutable path, but same-ID publication must
fail and the normal PR merge policy still applies. Record/receipt JSON-only PRs are workflow-only for
`scripts/ci_change_classifier.py`: they run fast ledger and queue validation without native Linux/Windows validation.
Include pending observation IDs in live status when a record or resolution is awaiting publication.

Assign one read-only QA role when subagent capacity permits. QA reviews issue selection risk, diff scope, regression
coverage, validation commands, GitHub Actions evidence, and merge readiness. QA must not claim issues, edit the
workbook, or start heavy validation unless the controller explicitly delegates a bounded validation task.

After selecting an exact issue, claim that row:

```bash
python3 scripts/issue_queue.py claim \
  --owner "$OWNER" \
  --lease-minutes 1440 \
  --issue "$ISSUE_NAME"
```

The claim branch and pull request must be workbook-only and must merge before implementation starts. After the claim PR
actually merges into `main`, create the implementation worktree from the updated `origin/main`, generate the worker
prompt, and assign exactly one worker to that implementation branch.

When a controller loop does not make any new claim, still fetch and inspect `origin/main` before deciding that work is
blocked or exhausted. Other claim, implementation, status, or reclaim PRs may have merged while the controller was
polling workers or CI; the next eligible set must come from the refreshed merged workbook.

The CLI considers a row mechanically eligible only when:

- status is `NOT_STARTED`;
- every issue in `Dependencies` is `DONE`;
- optional priority/epic/component filters match.

The CLI reports target-file overlaps as advisory metadata. The legacy `--allow-file-overlap` flag is still accepted for
older controller prompts, but exact overlap no longer changes mechanical eligibility by itself. Task payloads from
`list --json`, `show`, `next`, and `claim` include `Target File Overlap Policy` and `Active File Overlaps` fields for
direct-command review.

To claim an exact row:

```bash
python3 scripts/issue_queue.py claim \
  --owner "$OWNER" \
  --issue '[EPIC_01][STORY_01][SUBSTORY_01]Add explicit fight outcome model'
```

Generate the exact worker prompt after claiming:

```bash
python3 scripts/issue_queue.py prompt \
  --issue "$ISSUE_NAME" \
  --claim-id "$CLAIM_ID" \
  --owner "$OWNER"
```

Alternatively use `claim --format prompt`.

## Live worker status

Keep at least eight live subagents attached to the controller whenever the subagent interface is available. Keep at least
eight implementation issues active whenever eight status-and-dependency eligible implementation issues exist. Before
dispatching or refilling implementation workers, note current RAM, free disk, accumulated run/worktrees, prunable
worktree metadata, and running heavy build/test/coverage/Xvfb/MCP jobs so the controller avoids obvious resource
pressure without imposing a fixed RAM cap. If the controller cannot keep eight issue workers active, report the concrete
status, dependency, live-worker-status, resource, disk, cleanup, authentication, queue-validation, workbook-PR, or
repository-safety blocker.

Each controller instance must keep exactly four of its own workbook claim slots active whenever status-and-dependency
eligible issues are available for that controller. Healthy rows have a non-overdue heartbeat and a non-expired lease.
Heartbeat-overdue, lease-expired, suspect, and reclaimable rows do not count as healthy work, but they still occupy the
controller's capacity until a heartbeat, release, reclaim, or terminal-status workbook update actually merges. Run
`shortlist --controller-id "$CONTROLLER_ID"` before every refill and keep claiming only when
`controllerCapacity.fillableDeficit` is greater than zero. If `controllerCapacity.refillBlockedByRecovery` is true,
inspect and reconcile `controllerCapacity.recoveryIssues` before claiming more work. If
`controllerCapacity.overCapacity` is true, stop claiming and report `controllerCapacity.overLimitBy`.

Standby subagents may help with lightweight status polling, eligibility summaries, or review preparation only when fewer
than eight implementation issues are safe for non-source reasons. They must not claim issues, edit files, touch the
workbook, start builds, run tests, or launch coverage/Xvfb/MCP validation.

When eight implementation workers are not safe for non-source reasons, prefer assigning one standby subagent as the project manager so the next
refill decision has a current prioritization brief. When eight status-and-dependency eligible implementation issues
exist, the project manager should run as extra read-only capacity rather than displacing an implementation worker.

Assign one standby or extra read-only subagent as QA whenever capacity permits. QA reviews selection risk, diffs,
tests, GitHub Actions evidence, and merge readiness; it must not claim issues, edit the workbook, or start heavy
validation unless the controller assigns a bounded QA validation task.

Poll every active worker through the available subagent/task interface. If direct polling is unavailable, require
structured status updates from the worker.

After every controller loop iteration, cleanup audit, claim or pull-request status check, and before dispatching new
work, print a live status table containing at least:

- worker owner;
- controller ID;
- issue key;
- current phase;
- progress estimate;
- last reported action;
- changed files if known;
- current validation command if running;
- branch name;
- pull request number or pending PR state;
- current resource and disk state;
- cleanup state, including prunable worktree metadata and accumulated run/worktree size when known;
- open-PR audit summary, including any controller-owned PR requiring update, CI fix, human review, or never-touch
  recovery;
- pending workflow observation IDs and whether an observation-only or resolution-only PR is needed;
- project-manager prioritization brief state or the reason no project-manager subagent is available;
- QA review state or the reason no QA subagent is available;
- blockers;
- next controller action.

Do not rely on workbook fields for live status. The workbook records durable queue state; live worker state comes from
subagent polling or structured worker reports.

Run the read-only resource audit before every dispatch/refill decision, before heavy validation, after each controller
loop, and after merged-checkpoint cleanup:

```bash
python3 scripts/controller_resource_audit.py --json
```

The audit reports Git repository health, disk usage, active and prunable worktree registrations, and matching controller
run/worktrees such as `/tmp/nouraajd-*`, `/tmp/fall-of-nouraajd-codex`, and `/tmp/fon-workflow-optimizer-*`. It compares
local `refs/remotes/origin/main` with live `origin` output read-only, without fetching or mutating refs. It is report-only
by default. Treat audit errors such as unreadable Git state, unresolved `HEAD` or `origin/main`, zero-byte loose Git
objects, zero-byte Git ref files, or disk pressure as blockers to new heavy work, and treat warnings about stale
remote-tracking refs, prunable worktree metadata, or large accumulated run/worktrees as cleanup prompts before refilling
worker slots.

When auditing merge-policy drift or cleanup readiness, include the live GitHub branch-protection check:

```bash
python3 scripts/controller_resource_audit.py --json --skip-run-tree-sizes --github-repo lisu188/fall-of-nouraajd
```

`--skip-run-tree-sizes` is discovery-only. Its JSON output marks `runTrees.sizesMeasured` and each record's
`sizeMeasured` as `false`; run it without that flag before relying on run-tree byte totals for cleanup priority.

## Subagent progress protocol

A worker should report meaningful milestones to the controller after source inspection, root-cause analysis,
implementation, focused validation, and full validation. Workers must not update the workbook directly during queue
controller runs.

The queue reports `heartbeatDueAtUtc`, `heartbeatDueInMinutes`, and `heartbeatOverdue` in read-only task payloads. The
normal persisted heartbeat deadline is derived by the queue script and is shorter than the stale/reclaim-age threshold
(currently half of the 240-minute default). The controller should poll and confirm the worker is alive, persist a
heartbeat after meaningful milestones, and also persist one before the derived heartbeat deadline when the task remains
active. Never fabricate a heartbeat for an unreachable worker.

When the controller persists a heartbeat, it does so from a fresh workbook-only branch:

```bash
python3 scripts/issue_queue.py heartbeat \
  --issue "$ISSUE_NAME" \
  --claim-id "$CLAIM_ID" \
  --owner "$OWNER" \
  --progress 20 \
  --note 'Root cause verified in CFightHandler.cpp and CCreature.cpp' \
  --lease-minutes 1440
```

Every heartbeat preserves an existing later lease and extends the lease only when the requested renewal would move it
farther into the future. Recommended checkpoints are 5%, 20%, 70%, and 90%.

A single serialized heartbeat-only PR may update multiple claims owned by the same controller only when every worker was
individually polled, every issue, owner, and claim ID was validated, every edit is heartbeat-only, validation is
all-or-nothing, the PR lists every affected issue, and no claim, terminal-state, priority, dependency, or unrelated
workbook edit is mixed into the PR. Merge the workbook-only heartbeat PR before treating the heartbeat as durable.

Complete only after the implementation pull request has actually merged and validation results have been reviewed:

```bash
cat >/tmp/task-summary.txt <<'EOF'
Implemented the detailed fight result contract while preserving the bool compatibility API.
EOF

cat >/tmp/task-validation.txt <<'EOF'
focused local regression: PASS
python3 scripts/poll_pr_checks.py <PR_NUMBER>: PASS
EOF

python3 scripts/issue_queue.py complete \
  --issue "$ISSUE_NAME" \
  --claim-id "$CLAIM_ID" \
  --owner "$OWNER" \
  --summary-file /tmp/task-summary.txt \
  --validation-file /tmp/task-validation.txt
```

For local agents, prefer GitHub Actions polling as the default PR delivery path for heavy validation. After focused
local checks, open the pull request and satisfy compilation, native tests, performance guards, platform checks, the full
Python suite, and coverage by polling GitHub Actions instead of duplicating those heavy commands locally:

```bash
python3 scripts/poll_pr_checks.py <PR_NUMBER>
```

For coverage-relevant changes, the poller auto-requires the conditional coverage step when changed paths match the
workflow coverage rule. Passing `--require-step coverage` explicitly is still valid when the caller wants to force that
check:

```bash
python3 scripts/poll_pr_checks.py <PR_NUMBER> --require-step coverage
```

Run heavy local validation only when CI cannot cover the required evidence, a focused local reproduction is necessary
before opening the PR, or GitHub Actions polling is unavailable or blocked. Report focused local checks separately from
CI-polled validation. Passing the path-selected build workflow checks is sufficient PR delivery evidence for the
validation class selected by `scripts/ci_change_classifier.py`: native/source/content changes require Linux and Windows
build jobs, while workflow-only docs/prompts/tooling changes keep a terminal `linux` check but skip unrelated
native-heavy steps after focused workflow validation. It proves coverage only when the workflow's changed-path rule runs
its `coverage` step somewhere in the selected build workflow run, currently in the conditional `linux-coverage` job; the
poller auto-adds this step for coverage-relevant PR paths. Additional release, MCP gameplay, manual, or issue-specific
validation is needed only when the task targets that surface or the user
requests it.
Do not enable auto-merge until CI-polled validation passes when it is the only full-validation evidence.

Workbook-only queue-state PRs that update only `planning/fall_of_nouraajd_issue_proposals.xlsx` are different from
implementation PRs. After reviewing that the diff is XLSX-only and running `python3 scripts/issue_queue.py validate`,
merge the claim, terminal-status, heartbeat, reclaim, priority, dependency, or other approved queue-state PR immediately
with squash merge; do not wait for GitHub Actions to finish. If repository settings block direct merge, enable
auto-merge and continue controller work instead of idling on Actions.

If the implementation PR has already merged, stop waiting on its Actions run even if a poll command is still running.
Fetch `origin/main`, verify the merge, and proceed with the next controller step.

`DONE` requires a result summary, validation results, `Progress %=100`, and a completion timestamp. Do not mark `DONE`
while implementation auto-merge is merely queued.

## Block, fail, cancel, and release

Verified source or environment blocker:

```bash
python3 scripts/issue_queue.py block \
  --issue "$ISSUE_NAME" \
  --claim-id "$CLAIM_ID" \
  --owner "$OWNER" \
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

An `IN_PROGRESS` row has separate heartbeat and lease signals. `Updated At UTC` is the persisted heartbeat source, with
`Claimed At UTC` used only as compatibility fallback. `Lease Until UTC` protects ownership. A heartbeat-overdue claim
with a future lease is suspect but not timing-eligible for reclaim; an expired lease with a recent heartbeat is also
suspect but not timing-eligible for reclaim. Reclaim timing requires both an expired or missing lease and a missing or
overdue heartbeat. The effective boundary is the later of the lease expiry and the heartbeat-age threshold.

```bash
python3 scripts/issue_queue.py reclaim-stale --dry-run
python3 scripts/issue_queue.py reclaim-stale
```

The dry run lists stale rows without modifying the workbook and reports `activeClaims`, `staleCount`,
`reclaimableStaleCount`, and `reclaimSafety`. `staleCount` is heartbeat-overdue rows; `reclaimableStaleCount` is the
subset whose lease condition is also expired or missing. The default threshold is 240 minutes; pass
`--older-than-minutes` only when the controller has an explicit reason to use a different age. Dry-run rows include
heartbeat status, lease status, `reclaimableAtUtc`, `reclaimReason`, `timingEligible`, and `reclaimReady: false`.
Inspect the worker worktree, branch, pull request, and any recoverable changes before running the mutating command.
Run the mutating command only from a fresh workbook-only branch and publish it through the same serialized queue-state
PR process as claims and terminal statuses. The mutating command reclaims only timing-eligible rows, and reclaimed rows
are not eligible for dispatch until that reclaim PR actually merges. Reclaimed rows return to `NOT_STARTED`, retain the
incremented `Attempt`, and receive an audit note describing the previous owner and claim.

`validate` warns about heartbeat-overdue claims, expired leases, and timing-eligible reclaim candidates without failing
the workbook. `list --status IN_PROGRESS --json` includes derived heartbeat deadline, heartbeat overdue, lease expiry,
reclaim boundary, and claim-health fields for read-only controller status checks.

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
- Refill only after unresolved heartbeat-overdue, lease-expired, suspect, or reclaimable owned rows have been
  reconciled by a merged workbook heartbeat, release, reclaim, or terminal-status update.
- Do not run local native builds, `ctest`, full Python suites, or coverage for PR delivery unless a focused local
  reproduction is necessary or GitHub Actions cannot provide the needed evidence.
- Prefer CI polling for Linux full validation instead of duplicating heavy local build, test, and coverage work.
- Keep at least eight live subagents and at least eight active implementation issues whenever eight issues are
  status-and-dependency eligible, using standby roles only when fewer than eight implementation workers are safe for
  non-source reasons.
- Check resource pressure before dispatch/refill and before starting local heavy validation, but do not impose a fixed
  RAM cap. If missing worker status or actual resource pressure prevents safe dispatch, stop filling worker slots until
  the blocker clears.
- If disk pressure, prunable worktree metadata, or accumulated run/worktree usage prevent safe dispatch, stop
  filling worker slots until the blocker is reported or safely cleaned.
- Remove only completed clean worktrees. Use `git worktree prune` only for prunable metadata after reviewing that the
  corresponding worktree directories no longer exist. Do not delete branches unless explicitly asked.
