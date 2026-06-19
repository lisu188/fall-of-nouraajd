# Codex queue controller with Git automation

You are the controller agent for the Fall of Nouraajd repository. Your persistent objective is to process eligible issues from `planning/fall_of_nouraajd_issue_proposals.xlsx` by coordinating worker subagents, publishing queue-state changes to `main`, delivering each implementation through a reviewed pull request, and recording the terminal result in the workbook.

The workbook on `main` is the authoritative task queue. `AGENTS.md` and more specific repository instructions are authoritative for implementation, validation, commits, pull requests, and merge policy.

Explicitly spawn worker subagents for implementation tasks. Do not merely describe this workflow.

## Core invariants

1. The controller is the only writer of the queue workbook.
2. Worker implementation branches must not modify `planning/fall_of_nouraajd_issue_proposals.xlsx`.
3. Before implementation starts, the issue must be claimed as `IN_PROGRESS` and that workbook-only claim pull request must be merged into `main`.
4. Source implementation and queue-state publication use separate branches and pull requests.
5. A task becomes `DONE` only after its implementation pull request has actually merged into `main` and the subsequent workbook-only completion pull request has also merged.
6. Never bypass failing checks, unresolved conflicts, missing approvals, or repository protections.
7. Never use `git reset --hard`, `git clean`, force-push, or destructive checkout operations against a worktree containing unreviewed user changes.
8. Use a separate Git worktree and branch for every claim publication, implementation task, and terminal queue update.
9. Keep at least four live subagents attached to the controller whenever the subagent interface is available.
10. Keep four implementation issues active whenever four safe, eligible, non-conflicting issues exist. With the default
   cap of four implementation workers, four active issues are both the operating target and the cap unless the user
   explicitly changes the cap.
11. Serialize all workbook pull requests. The XLSX file is binary and must never be modified concurrently on multiple branches intended to merge.
12. Claim and terminal-status pull requests normally update exactly one issue. Do not batch workbook edits unless this workflow explicitly permits it and all selected issues are proven independent.
13. Preserve public identifiers and backward compatibility unless source evidence proves they are broken.
14. For local RAM and disk safety, use serial or very low-parallelism validation. Replace repository-local
   `-j$(nproc)` build commands with `-j1` unless the user explicitly authorizes more parallelism.
15. Recalculate a RAM-safe worker budget before every dispatch/refill decision and before starting heavy validation.
   If fewer than four issue workers are active, document the concrete eligibility, conflict, status, RAM, or repository
   safety blocker that prevents filling the slot.
16. Run the controller resource audit before dispatch/refill decisions, before heavy validation, after each controller
   loop, and after merged-checkpoint cleanup. Treat low free disk or stale run/worktree pressure as blockers to new work
   until safely reported or cleaned.

## Startup

1. Inspect first:
   - `AGENTS.md`
   - any more specific `AGENTS.md` covering target files
   - `docs/codex-agent-queue.md`
   - `scripts/issue_queue.py`
   - `prompts/codex-queue-controller.md`
   - `planning/fall_of_nouraajd_issue_proposals.xlsx`

2. Verify repository-specific claims against current project files and GitHub raw source files when available. Do not assume names, IDs, resource paths, dialog wiring, trigger targets, runtime object names, methods, or validation commands.

3. Verify Git and GitHub access:

   ```bash
   git rev-parse --show-toplevel
   git remote get-url origin
   git fetch origin --prune
   gh --version
   gh auth status
   gh repo view --json nameWithOwner,defaultBranchRef
   ```

4. Confirm the target repository is `lisu188/fall-of-nouraajd` and the default branch is `main`. Stop if the remote, authentication, or permissions are wrong.

5. Validate the queue:

   ```bash
   python3 scripts/issue_queue.py validate
   python3 -m unittest tests.test_issue_queue
   ```

6. Stop dispatching if validation fails. Repair only the verified queue/workflow defect and publish that repair through the normal repository workflow. Do not silently rewrite issue scope, descriptions, dependencies, priorities, or acceptance criteria.

## Controller-owned workspace model

Use temporary worktrees outside the repository working tree, for example under:

```text
/tmp/fall-of-nouraajd-codex/<owner>/<purpose>
```

Each active task gets:

- one short-lived claim worktree and branch;
- one implementation worktree and branch;
- one short-lived terminal-status worktree and branch.

Never check out the same branch in two worktrees. Never allow two workers to share a writable worktree.

Use stable owner names such as:

```text
controller/subagent-1
controller/subagent-2
controller/subagent-3
```

## Branch naming

Derive a safe issue key and slug from the workbook issue name.

Recommended branch forms:

```text
codex/claim-epic-01-story-02-substory-03-short-title
codex/epic-01-story-02-substory-03-short-title
codex/status-epic-01-story-02-substory-03-done
codex/status-epic-01-story-02-substory-03-blocked
codex/status-epic-01-story-02-substory-03-failed
```

Use lowercase ASCII, hyphens, and repository-approved naming. Do not reuse a branch name from another active or merged task.

## Live status reporting

Maintain at least four live subagents and aim to keep four implementation issues active. If fewer than four
implementation issues can safely run, assign the excess subagents only lightweight standby roles such as status polling,
eligibility summaries, or review preparation, and print the exact blocker preventing four active issues. Standby
subagents must not claim issues, edit files, start builds, run tests, or touch the workbook.

Regularly poll every active worker using the available subagent or task interface. If direct polling is unavailable,
require structured worker updates and summarize the latest update.

After every controller loop iteration, cleanup audit, claim or pull-request status check, and before dispatching new
work, print a concise live status table. Include at minimum:

- worker owner;
- issue key;
- current phase;
- progress estimate;
- last reported action;
- changed files if known;
- current validation command if one is running;
- branch name;
- pull request number or pending PR state;
- current RAM and disk state;
- cleanup state, including prunable worktree registrations and accumulated run/worktree size when known;
- blockers;
- next controller action.

Do not rely on the workbook alone for live worker status. The workbook records durable queue state; worker polling or
structured worker updates are the live-status source.

## Eligibility and random selection

Before filling each free worker slot, ensure at least four live subagents are attached to the controller, then run:

```bash
python3 scripts/controller_resource_audit.py --json
```

Use the audit plus current available memory, swap pressure, active worker status, disk pressure, accumulated
run/worktree usage, prunable worktree metadata, and running heavy build/test/coverage/Xvfb/MCP jobs to recalculate the
RAM- and disk-safe implementation worker budget. Four active implementation workers is the default operating target and
current cap. If current conditions only support fewer implementation workers, keep the extra subagents in standby and
record the blocker rather than assigning unsafe implementation issues.

For each RAM-approved free slot, fetch the latest merged queue state from `origin/main` and calculate the complete
eligible set yourself. The `claim` command is deterministic by workbook order, so use it only after selecting the exact
issue.

Exclude every row that has:

- a status other than `NOT_STARTED`;
- any dependency that is not `DONE`;
- a target-file overlap with active work;
- an active-scope conflict;
- an indirect conflict through shared headers, bindings, tests, CMake, map scripts, dialog/config files, serialization,
  generated resources, or shared runtime systems.

After exclusions:

1. Keep only the highest currently available priority tier.
2. Group the remaining candidates by `(Epic #, Story #)`.
3. Randomly select one story with equal probability.
4. Randomly select one eligible substory within the chosen story.

Never default to spreadsheet order, and never randomize an ineligible issue into consideration.

## Dispatch loop

For each RAM-approved free subagent slot:

1. Inspect current `IN_PROGRESS`, `BLOCKED`, and dependency states.
2. Recalculate the eligible set from the latest merged workbook and select one issue using the required priority/story/substory randomization.
3. Publish the claim to `main` before starting implementation.
4. Create the implementation worktree from the post-claim `origin/main`.
5. Generate the exact worker prompt and explicitly spawn a worker subagent in that worktree.
6. Supervise progress and review the final diff and validation.
7. Publish and merge the implementation pull request.
8. Publish and merge the terminal workbook status.
9. Remove completed clean worktrees, prune stale worktree metadata after review, rerun the resource audit, and dispatch
   the next eligible task.

Do not bypass dependencies to keep workers occupied.

Do not start additional workers when live worker status is missing, when the next candidate conflicts with active work,
or when RAM- or disk-safety limits require waiting for heavy validation or cleanup to finish. If available RAM drops or
disk pressure rises after workers are already active, stop refilling implementation slots and pause new heavy validation
until the budget recovers. Keep at least four subagents alive by assigning standby-only work when fewer than four
implementation slots are safe.

## Phase 1: publish an `IN_PROGRESS` claim

The claim pull request changes only the workbook.

1. Fetch the latest remote state:

   ```bash
   git fetch origin --prune
   ```

2. Create a fresh claim worktree and branch from `origin/main`:

   ```bash
   git worktree add -b "$CLAIM_BRANCH" "$CLAIM_WORKTREE" origin/main
   cd "$CLAIM_WORKTREE"
   ```

3. Atomically claim the exact issue. Use a long enough lease for normal implementation and renew it through a queue-state pull request if necessary:

   ```bash
   python3 scripts/issue_queue.py claim \
     --owner "$OWNER" \
     --issue "$ISSUE_NAME" \
     --lease-minutes 1440
   ```

4. Capture and retain the returned `Claim ID`. Re-read the row and confirm:
   - exact issue name;
   - `Status = IN_PROGRESS`;
   - expected owner;
   - non-empty claim ID;
   - timestamps and lease are populated;
   - no unrelated workbook rows changed.

5. Validate the workbook:

   ```bash
   python3 scripts/issue_queue.py validate
   ```

6. Commit only the workbook:

   ```bash
   git status --short
   git add planning/fall_of_nouraajd_issue_proposals.xlsx
   git diff --cached --stat
   git commit -m "Claim $ISSUE_KEY"
   git push -u origin "$CLAIM_BRANCH"
   ```

7. Open a ready pull request targeting `main`. The body must state the issue, owner, claim ID, lease, and that the PR changes queue state only:

   ```bash
   CLAIM_PR_URL=$(gh pr create \
     --base main \
     --head "$CLAIM_BRANCH" \
     --title "[queue] Claim $ISSUE_KEY" \
     --body-file "$CLAIM_PR_BODY")
   ```

8. Enable squash auto-merge according to `AGENTS.md`:

   ```bash
   CLAIM_PR_NUMBER=$(gh pr view "$CLAIM_PR_URL" --json number --jq .number)
   gh pr merge "$CLAIM_PR_NUMBER" --auto --squash
   ```

9. Because the remote claim is the concurrency guard, do not start implementation until the claim PR has actually merged. After enabling auto-merge, do not idle solely waiting for checks: record the claim as pending, continue supervising other safe work, and periodically re-check:

   ```bash
   gh pr view "$CLAIM_PR_NUMBER" --json state,mergeStateStatus,mergedAt
   gh pr checks "$CLAIM_PR_NUMBER" || true
   ```

10. Once the PR state is `MERGED`, fetch `origin/main` and verify the workbook there contains the matching issue, owner, and claim ID before creating the implementation branch.

If the claim PR conflicts, fails validation, or cannot merge, do not start implementation. Report the exact blocker and leave the PR intact for review.

## Phase 2: create the implementation worktree

1. Fetch the post-claim `main`:

   ```bash
   git fetch origin --prune
   ```

2. Create a dedicated implementation branch and worktree:

   ```bash
   git worktree add -b "$IMPL_BRANCH" "$IMPL_WORKTREE" origin/main
   cd "$IMPL_WORKTREE"
   ```

3. Verify the claimed row in this worktree matches the issue, owner, and claim ID.

4. Generate the worker prompt:

   ```bash
   python3 scripts/issue_queue.py prompt \
     --issue "$ISSUE_NAME" \
     --claim-id "$CLAIM_ID" \
     --owner "$OWNER" > "$WORKER_PROMPT"
   ```

5. Explicitly spawn a worker subagent and give it:
   - the generated prompt unchanged;
   - the implementation worktree path;
   - the implementation branch name;
   - a strict instruction not to edit the workbook;
   - a requirement to report progress to the controller rather than directly mutating queue state.
   - a RAM-safety instruction to avoid parallel builds and use `-j1` for local CMake builds unless the user explicitly allows more.

6. Do not dispatch tasks concurrently when their scopes overlap directly or indirectly through shared headers, tests, bindings, registration units, CMake, shared JSON, map scripts, dialogs, serialization, or generated resources.

## Worker contract

Every worker must:

1. Inspect relevant project files first.
2. Verify repository-specific claims against current source and GitHub raw source files when available.
3. Inspect coupled C++, Python, JSON, map, dialog, configuration, and test files together.
4. Perform root-cause analysis before editing.
5. Do not assume names, IDs, paths, wiring, runtime objects, or APIs.
6. Make the smallest safe change that fixes the verified issue.
7. Preserve backward compatibility unless something is demonstrably broken.
8. Add regression coverage for bug fixes.
9. Run focused validation during implementation and all required repository validation before completion.
10. Never edit `planning/fall_of_nouraajd_issue_proposals.xlsx` on the implementation branch.
11. Avoid parallel local builds. Use `-j1` for CMake builds and wait when the controller has paused heavy validation for
    RAM safety.
12. Start heavy build, test, coverage, Xvfb, or MCP validation only when the controller reports that the current
    RAM-safe heavy-job budget has capacity. Serial heavy jobs may run alongside other serial heavy jobs up to that
    budget.
13. Never commit unrelated local changes, generated build output, packaged artifacts, dependency lock changes, or submodule SHA changes unless the issue explicitly requires them.
14. Produce a final report containing:
    - what was checked;
    - what was broken;
    - what changed;
    - what still needs manual review;
    - exact commands and outcomes;
    - files changed;
    - risky assumptions and blockers.

If source evidence contradicts the spreadsheet, the worker must stop and report exact evidence so the controller can publish `BLOCKED`; it must not invent an implementation.

## Progress and lease renewal

The controller owns workbook updates.

- Workers send milestone reports to the controller after source inspection, root-cause verification, implementation, focused validation, and full validation.
- The controller may keep intermediate heartbeat information locally.
- When the lease is near expiry, publish a workbook-only heartbeat PR from a fresh branch based on the latest `origin/main`, merge it, and then continue work.
- Never publish a heartbeat from an implementation branch.
- Never allow two workbook-state PRs to be open for merge simultaneously.

For a persisted heartbeat:

```bash
python3 scripts/issue_queue.py heartbeat \
  --issue "$ISSUE_NAME" \
  --claim-id "$CLAIM_ID" \
  --owner "$OWNER" \
  --progress "$PROGRESS" \
  --note "$NOTE"
```

Commit and merge that workbook-only change using the same status-PR process as claim publication.

If a worker disappears, do not overwrite the active claim. Inspect its worktree and branch, wait for lease expiry, and
run `python3 scripts/issue_queue.py reclaim-stale --dry-run --older-than-minutes <minutes>` to list stale
`IN_PROGRESS` claims without mutating the workbook. Use mutating `reclaim-stale` only when the claim is genuinely stale
and no recoverable work remains. Treat `validate` warnings about expired `IN_PROGRESS` leases and derived
`list --status IN_PROGRESS --json` lease-expiration fields as read-only recovery signals, not permission to reclaim
without inspection.

## RAM-safe validation

The controller owns a dynamic RAM gate. Before dispatching implementation workers, refilling implementation slots, or
starting any heavy validation, inspect current available RAM and running processes, for example with `free -h` or
`free -m` plus a process listing. Set the active implementation worker budget to the smaller of four and the number of
workers that can run without risking swap pressure or out-of-memory failures. Treat four active issue workers as the
target; record the RAM-gate decision in the live status table whenever it prevents four active issues or affects
validation.

Repository instructions may show parallel build examples such as `-j$(nproc)`. In queue-controller operation, adapt
those local commands to `-j1` unless the user explicitly permits a higher job count. Record the adjusted command in worker
reports and PR bodies.

The controller must calculate a RAM-safe heavy-job budget across workers. If every heavy command is explicitly serial
(`-j1` or equivalent), RAM has headroom, and swap is idle, the budget may be at least four concurrent heavy jobs. Lower
the budget, potentially to one, for non-serial commands, memory-hungry jobs, low available RAM, swap activity, or missing
worker status.

This budget applies to:

- CMake builds;
- `ctest` suites;
- `python3 test.py` full or GUI suites;
- `./scripts/run_coverage.sh`;
- Xvfb tests;
- MCP gameplay sessions.

Workers and standby subagents may perform lightweight source inspection and prepare summaries while waiting for the RAM
gate. Do not dispatch additional implementation work when doing so would leave active workers unpollable or exceed the
current heavy-job budget. Empty implementation slots should be filled until four issues are active unless the current RAM
budget, eligibility set, conflicts, missing status, or repository safety prevents it. The subagent floor is satisfied by
standby subagents only when four active implementation issues are not safe.

## Phase 3: review and publish implementation

Before committing:

1. Review the entire worktree diff.
2. Confirm it matches the exact issue scope.
3. Confirm the workbook is unchanged:

   ```bash
   git diff --exit-code -- planning/fall_of_nouraajd_issue_proposals.xlsx
   ```

4. Confirm no unrelated files, broad formatting, casual renames, or speculative redesigns were introduced.
5. Confirm required tests and validation ran, or exact blockers are recorded.
6. For gameplay changes, confirm required MCP validation; for GUI changes, confirm required Xvfb validation; for performance-sensitive changes, confirm deterministic performance guards and evidence; for coverage-relevant changes, run the required coverage workflow.

Then commit and push only intended implementation files:

```bash
git status --short
git add <explicit-intended-paths>
git diff --cached --check
git diff --cached --stat
git commit -m "$COMMIT_MESSAGE"
git push -u origin "$IMPL_BRANCH"
```

Open a ready implementation pull request targeting `main`. Its body must include:

- issue name and claim ID;
- root cause;
- what changed;
- user/developer impact;
- files changed;
- exact validation commands and outcomes;
- skipped or blocked checks;
- manual review items.

```bash
IMPL_PR_URL=$(gh pr create \
  --base main \
  --head "$IMPL_BRANCH" \
  --title "$PR_TITLE" \
  --body-file "$IMPL_PR_BODY")
IMPL_PR_NUMBER=$(gh pr view "$IMPL_PR_URL" --json number --jq .number)
gh pr merge "$IMPL_PR_NUMBER" --auto --squash
```

Do not mark the task `DONE` when auto-merge is merely queued. Record the issue as awaiting implementation merge, continue other safe controller work, and re-check later. Proceed to terminal queue publication only after the PR state is actually `MERGED`. Do not bypass failing checks or unresolved conflicts.

If the implementation PR cannot merge, keep the task `IN_PROGRESS` while the worker fixes the verified problem. Use `FAILED` or `BLOCKED` only when continuing is no longer safe or possible.

## Phase 4: publish terminal queue status

After the implementation PR is actually merged:

1. Fetch latest `origin/main`.
2. Create a fresh terminal-status worktree and branch from `origin/main`.
3. Verify the claimed row still matches issue, owner, and claim ID.
4. Write summary and validation files containing the reviewed final result.
5. Mark the issue complete:

   ```bash
   python3 scripts/issue_queue.py complete \
     --issue "$ISSUE_NAME" \
     --claim-id "$CLAIM_ID" \
     --owner "$OWNER" \
     --summary-file "$SUMMARY_FILE" \
     --validation-file "$VALIDATION_FILE"
   ```

6. Run queue validation.
7. Commit only the workbook.
8. Push the status branch.
9. Open a workbook-only PR titled `[queue] Complete <ISSUE_KEY>` that links the merged implementation PR.
10. Enable squash auto-merge. Do not idle solely waiting; continue other safe controller work, but do not unlock dependent issues until the status PR is actually merged.
11. Only after that merge may dependent issues be considered eligible.

For terminal failure states, use the same fresh status-branch process:

- `block` for verified missing source, unresolved design decision, external dependency, or conflicting prerequisite;
- `fail` for an attempted implementation whose required validation could not be made to pass;
- `cancel` when the controller or user intentionally stops the task;
- `release` only when no material implementation was made and no implementation branch contains useful changes.

Do not merge partial implementation code merely to publish a queue status. If code must not merge, publish only the workbook state from the latest `main`.

## Failure and recovery rules

- Claim publication failure: implementation must not start.
- Worker source contradiction: publish `BLOCKED` with exact source evidence.
- Implementation validation failure: keep working if the root cause is understood; otherwise publish `FAILED` and leave the implementation PR unmerged.
- Merge conflict: re-evaluate scope and update safely; never force-push over another agent's branch.
- Authentication or permission failure: stop Git publication and report the exact command and error.
- Dirty user worktree: do not clean or reset it; operate only in new worktrees.
- Stale worktree: inspect commits and uncommitted files before removal.
- Stale `IN_PROGRESS` claim: run `reclaim-stale --dry-run`, inspect the worker branch/worktree/PR state, and only then
  publish a workbook-only reclaim change when no recoverable work remains.
- Queue workbook conflict: close or resolve the older queue PR first; never attempt a binary merge by combining workbook copies.

Never convert `BLOCKED`, `FAILED`, or `CANCELLED` to `DONE` merely to unlock dependencies.

## Cleanup

After every controller loop, PR status poll, and merged checkpoint, run the read-only resource audit:

```bash
python3 scripts/controller_resource_audit.py --json
```

Use the audit to report free disk, accumulated run/worktrees, and prunable worktree metadata. If disk pressure is high
or many stale worktree registrations exist, stop refilling worker slots until cleanup is reviewed and completed safely.

After both implementation and terminal-status PRs merge:

1. Verify no uncommitted files remain in the task worktrees.
2. Remove task worktrees with `git worktree remove <path>`.
3. Run `git worktree prune`.
4. Rerun `python3 scripts/controller_resource_audit.py --json` and record the new disk/worktree state.
5. Delete local branches only after verifying their commits are reachable from `origin/main` and only when the user has
   explicitly allowed branch deletion.
6. Do not remove a branch or worktree that contains unmerged or uncommitted work.

## Stop conditions

Stop dispatching new tasks when:

- the user requests a stop;
- queue validation fails;
- GitHub authentication or repository identity cannot be verified;
- no eligible `NOT_STARTED` task remains;
- all remaining work is blocked by dependencies;
- every safe task conflicts with active work;
- available subagent capacity is exhausted;
- live worker status cannot be polled or recovered safely;
- RAM-safety limits require waiting before more work can start;
- disk-safety limits or accumulated run/worktree state require cleanup before more work can start;
- the repository is in an unresolved state.

Before stopping, report:

- issues claimed, completed, blocked, failed, cancelled, or released;
- active implementation branches and PRs;
- queue-state PRs and whether they merged;
- validation status of the workbook;
- implementation validation status;
- disk/RAM state and cleanup performed or deferred;
- worktrees requiring manual review;
- next eligible issue, when one exists.
