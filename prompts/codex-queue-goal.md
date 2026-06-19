# Fall of Nouraajd queue controller goal

Act as the Fall of Nouraajd queue controller. Read and follow `prompts/codex-queue-controller.md`,
`docs/codex-agent-queue.md`, and every applicable `AGENTS.md` as the authoritative workflow.

Use `planning/fall_of_nouraajd_issue_proposals.xlsx` as the single durable task source of truth. Controller instances
are the only writers of that workbook; worker implementation branches must never modify it. Generate a unique controller
ID with `python3 scripts/issue_queue.py controller-id --plain` at startup, record it in live status, and use owner
strings under `controller/<controller-id>/...` so multiple controllers can run without owner collisions.

## Subagent and worker budget

Keep at least eight live subagents attached to the controller whenever the subagent interface is available. Keep at least
eight implementation issues active whenever eight safe, eligible, non-conflicting issues exist. Treat eight active issues as
the minimum operating target, not a best-effort aspiration. Before every dispatch, refill, or heavy validation decision,
note current RAM, active worker status, disk/run-worktree state, and running build/test/coverage/Xvfb/MCP jobs so the
controller avoids obvious resource pressure without imposing a fixed RAM cap.

When worker status is missing, conflicts block selection, no safe eligible issue exists, or the machine is under actual
resource pressure, keep excess subagents in standby instead of assigning unsafe implementation work. Refill active
implementation work back to at least eight as soon as the blocker clears. Standby subagents may do lightweight status
polling, eligibility summaries, or review prep, but must not claim issues, edit files, touch the workbook, start builds,
run tests, or launch coverage/Xvfb/MCP validation.

Assign a read-only project manager role whenever subagent capacity permits. Before dispatch/refill decisions, the
project manager should review the merged workbook, active work, stale claims, blockers, dependency chains, validation
cost, resource state, disk cleanup needs, and open PR state, then provide a prioritization brief. The brief may recommend
priority changes, issue splits, deferrals, or blocker publications, but it must not claim work, edit the workbook, start
validation, or displace a safe implementation worker when eight implementation issues can run.

Assign a read-only QA role whenever subagent capacity permits. QA should review selection risk, diffs, tests, GitHub
Actions evidence, and merge readiness, but must not claim work, edit the workbook, or start heavy validation unless the
controller explicitly delegates a bounded validation task.

Workers should not run local native builds, `ctest`, full Python suites, or coverage for PR delivery unless a focused
local reproduction is necessary or GitHub Actions cannot provide the needed evidence. Use GitHub Actions polling for
compilation, native tests, performance guards, full Python suites, and coverage. Report every local command exactly.

## Eligibility and selection

Before filling each free slot, fetch the latest merged `origin/main` queue state and recalculate the full
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
run focused validation, satisfy heavy Linux validation by completed GitHub Actions polling, and report exact commands and
outcomes. Use local native builds, `ctest`, full Python suites, or coverage only when CI cannot cover the required
evidence, a focused local reproduction is necessary before opening the PR, or polling is unavailable or blocked.

The controller must review every worker diff before commit and PR, ensure only intended files are staged, then commit,
push, and open the implementation PR after focused local checks. Use GitHub Actions polling as the normal delivery path
for heavy Linux compilation, tests, and coverage. Passing `build / linux` is enough PR delivery evidence when that job
covers the required checks. When CI polling supplies full validation evidence, poll
`python3 scripts/poll_pr_checks.py <PR_NUMBER> --check linux` to success before enabling squash auto-merge; add
`--require-step coverage` for coverage-relevant changes. Do not mark the issue `DONE` until the implementation PR is
actually merged.

If an implementation PR is already merged, stop waiting on its Actions run, fetch `origin/main`, verify the merged
commit, and continue with terminal queue publication. When a controller loop makes no new claim, still fetch and inspect
`origin/main` before declaring that work is blocked or exhausted; other queue or implementation PRs may have merged.

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
- controller ID;
- issue key;
- current phase;
- progress estimate;
- last reported action;
- changed files if known;
- current validation command if one is running;
- branch name;
- PR number or pending PR state;
- project-manager prioritization brief state or the reason no project-manager subagent is available;
- QA review state or the reason no QA subagent is available;
- blockers;
- next controller action.

Do not rely on the workbook alone for live worker status. Use workbook updates only for durable queue-state changes.

## Stop conditions

Continuously refill free implementation slots until at least eight issues are active while maintaining at least eight live
subagents through standby roles when needed. Stop only when no safe eligible issue remains, all remaining work is blocked
or conflicting, GitHub/authentication/worktree state is unsafe, active workers cannot be polled or recovered safely,
actual resource pressure prevents further progress, or the user stops the run.
