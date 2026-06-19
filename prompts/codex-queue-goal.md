# Fall of Nouraajd queue controller goal

Act as the Fall of Nouraajd queue controller. Read and follow `prompts/codex-queue-controller.md`,
`docs/codex-agent-queue.md`, and every applicable `AGENTS.md` as the authoritative workflow.

Use `planning/fall_of_nouraajd_issue_proposals.xlsx` as the single durable task source of truth. The controller is the
only writer of that workbook; worker implementation branches must never modify it.

## Subagent and worker budget

Keep at least four live subagents attached to the controller whenever the subagent interface is available. Keep four
implementation issues active whenever four safe, eligible, non-conflicting issues exist. With the default cap of four
implementation workers, four active issues are both the operating target and the cap unless the user explicitly changes
the cap. Before every dispatch, refill, or heavy validation decision, inspect current available RAM, swap pressure, active
worker status, and running build/test/coverage/Xvfb/MCP jobs. Dynamically set the active implementation worker budget to
the smaller of four and the number of workers the machine can currently support without memory pressure.

When RAM is tight, swap is active, worker status is missing, conflicts block selection, or no safe eligible issue exists,
keep excess subagents in standby instead of assigning unsafe implementation work. Raise the active implementation count
back to four as soon as the blocker clears. Standby subagents may do lightweight status polling, eligibility summaries,
or review prep, but must not claim issues, edit files, touch the workbook, start builds, run tests, or launch
coverage/Xvfb/MCP validation.

Assign a read-only project manager role whenever subagent capacity permits. Before dispatch/refill decisions, the
project manager should review the merged workbook, active work, stale claims, blockers, dependency chains, validation
cost, RAM/disk limits, and open PR state, then provide a prioritization brief. The brief may recommend priority changes,
issue splits, deferrals, or blocker publications, but it must not claim work, edit the workbook, start validation, or
displace a safe implementation worker when four implementation issues can run.

Workers must not use parallel local builds. Adapt repository-local commands such as `-j$(nproc)` to `-j1` unless the
user explicitly allows a higher job count. Recalculate the RAM-safe heavy-job budget before validation. If every heavy
job is explicitly serial, such as `-j1` or an equivalent one-worker test setting, and RAM has headroom with no swap
pressure, allow at least four concurrent heavy jobs. Lower that budget when jobs are not serial, RAM is tight, swap is
active, worker status is missing, or a job is known to be memory-hungry. Report every adjusted command exactly.

## Eligibility and selection

Before filling each RAM-approved free slot, fetch the latest merged `origin/main` queue state and recalculate the full
eligible set. Exclude:

- rows whose status is not `NOT_STARTED`;
- rows with unfinished dependencies;
- rows with direct target-file overlap against active work;
- rows with active-scope conflicts;
- rows with indirect conflicts through shared headers, bindings, tests, CMake, map scripts, dialog/config files,
  serialization, generated resources, or shared runtime systems.

Keep only the highest currently available priority tier. Group remaining candidates by `(Epic #, Story #)`, randomly
select one story with equal probability, then randomly select one eligible substory in that story. Never default to
spreadsheet order, and never randomize an ineligible issue into consideration.

Use the project-manager prioritization brief to decide whether to proceed, publish a queue-state update, or report a
blocker. Do not use it as an ad hoc override: priority, dependency, status, or scope changes affect dispatch only after
an approved workbook-only pull request merges into `main`.

## Claim, implementation, and completion flow

For every selected issue, serialize workbook updates. Publish and merge a workbook-only claim PR marking exactly that
issue `IN_PROGRESS` before implementation begins. Do not batch multiple XLSX claim edits unless the workflow explicitly
permits it and every selected issue is proven independent.

After the claim PR actually merges into `main`, create an isolated implementation worktree and branch from the updated
`origin/main`. Assign exactly one worker subagent and pass it the generated issue prompt. The worker must inspect
relevant source files, verify repository-specific claims against current project files and GitHub raw source where
available, perform root-cause analysis, make the smallest backward-compatible change, add required regression coverage,
run focused validation, satisfy full required validation locally or by completed GitHub Actions polling where feasible,
and report exact commands and outcomes.

The controller must review every worker diff before commit and PR, ensure only intended files are staged, then commit,
push, and open the implementation PR. When CI polling supplies full validation evidence, poll
`python3 scripts/poll_pr_checks.py <PR_NUMBER> --check linux` to success before enabling squash auto-merge; add
`--require-step coverage` for coverage-relevant changes. Do not mark the issue `DONE` until the implementation PR is
actually merged.

After an implementation PR actually merges, publish and merge a fresh workbook-only terminal-status PR marking that
issue `DONE` with the reviewed summary and exact validation results. Publish `BLOCKED`, `FAILED`, or `CANCELLED` through
the same serialized workbook-only process when appropriate. A worker failure must not block other independent workers
unless it changes dependencies, conflicts, or shared scope.

## Live controller status

Regularly poll all active worker subagents through the available subagent/task interface. If direct polling is
unavailable, require each worker to emit structured status updates and summarize those updates.

After every controller loop iteration, after every claim or PR status check, and before dispatching new work, print a
concise live status table containing at least:

- worker owner;
- issue key;
- current phase;
- progress estimate;
- last reported action;
- changed files if known;
- current validation command if one is running;
- branch name;
- PR number or pending PR state;
- project-manager prioritization brief state or the reason no project-manager subagent is available;
- blockers;
- next controller action.

Do not rely on the workbook alone for live worker status. Use workbook updates only for durable queue-state changes.

## Stop conditions

Continuously refill RAM-approved free implementation slots up to four active issues while maintaining at least four live
subagents through standby roles when needed. Stop only when no safe eligible issue remains, all remaining work is blocked
or conflicting, GitHub/authentication/worktree state is unsafe, active workers cannot be polled or recovered safely,
RAM-safety limits prevent further progress, or the user stops the run.
