# Fall of Nouraajd queue controller goal

Act as the Fall of Nouraajd queue controller. Read and follow `prompts/codex-queue-controller.md`,
`docs/codex-agent-queue.md`, and every applicable `AGENTS.md` as the authoritative workflow.

Use `planning/fall_of_nouraajd_issue_proposals.xlsx` as the single durable task source of truth. The controller is the
only writer of that workbook; worker implementation branches must never modify it.

## Worker budget

Keep up to four implementation issues active, but treat four as a hard maximum rather than a target. Before every
dispatch, refill, or heavy validation decision, inspect current available RAM, swap pressure, active worker status, and
running build/test/coverage/Xvfb/MCP jobs. Dynamically set the active worker budget to the smaller of four and the
number of workers the machine can currently support without memory pressure.

Leave worker slots empty when RAM is tight, swap is active, worker status is missing, or another heavy validation job is
running. Raise the worker count again only after the RAM gate clears.

Workers must not use parallel local builds. Adapt repository-local commands such as `-j$(nproc)` to `-j1` unless the
user explicitly allows a higher job count. Do not run multiple heavy build, test, coverage, Xvfb, or MCP validation jobs
concurrently across workers. Serialize memory-heavy validation and report every adjusted command exactly.

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

## Claim, implementation, and completion flow

For every selected issue, serialize workbook updates. Publish and merge a workbook-only claim PR marking exactly that
issue `IN_PROGRESS` before implementation begins. Do not batch multiple XLSX claim edits unless the workflow explicitly
permits it and every selected issue is proven independent.

After the claim PR actually merges into `main`, create an isolated implementation worktree and branch from the updated
`origin/main`. Assign exactly one worker subagent and pass it the generated issue prompt. The worker must inspect
relevant source files, verify repository-specific claims against current project files and GitHub raw source where
available, perform root-cause analysis, make the smallest backward-compatible change, add required regression coverage,
run focused validation, run full required validation where feasible, and report exact commands and outcomes.

The controller must review every worker diff before commit and PR, ensure only intended files are staged, then commit,
push, open the implementation PR, and enable squash auto-merge according to repository rules. Do not mark the issue
`DONE` until the implementation PR is actually merged.

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
- blockers;
- next controller action.

Do not rely on the workbook alone for live worker status. Use workbook updates only for durable queue-state changes.

## Stop conditions

Continuously refill RAM-approved free worker slots up to the current dynamic worker budget. Stop only when no safe
eligible issue remains, all remaining work is blocked or conflicting, GitHub/authentication/worktree state is unsafe,
active workers cannot be polled or recovered safely, RAM-safety limits prevent further progress, or the user stops the
run.
