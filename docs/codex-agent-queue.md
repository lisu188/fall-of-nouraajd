# Local Codex agent queue

This workflow lets one controller Codex process coordinate several local subagents while the committed XLSX workbook remains the canonical task queue. It deliberately does not automate branches, commits, pushes, merges, or pull requests.

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

The queue lock prevents duplicate task claims. It does **not** prevent two subagents from editing the same source file. By default `claim` skips tasks whose exact `Target Files / Modules` overlap an existing `IN_PROGRESS` row. The controller must still inspect scopes and serialize work when shared headers, generated files, or indirectly coupled modules are involved.

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

Claim one task for each subagent:

```bash
python3 scripts/issue_queue.py claim \
  --owner controller/subagent-1 \
  --lease-minutes 120
```

`claim` selects the first eligible row by priority (`P0`, `P1`, `P2`) and epic/story/substory order. A row is eligible only when:

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

## Subagent progress protocol

A worker should update the same workbook after meaningful milestones:

```bash
python3 scripts/issue_queue.py heartbeat \
  --issue "$ISSUE_NAME" \
  --claim-id "$CLAIM_ID" \
  --owner controller/subagent-1 \
  --progress 20 \
  --note 'Root cause verified in CFightHandler.cpp and CCreature.cpp'
```

Every heartbeat extends the lease. Recommended checkpoints are 5%, 20%, 70%, and 90%.

Complete only after validation is finished:

```bash
cat >/tmp/task-summary.txt <<'EOF'
Implemented the detailed fight result contract while preserving the bool compatibility API.
EOF

cat >/tmp/task-validation.txt <<'EOF'
cmake --build cmake-build-release --target _game for_unit_tests -j$(nproc): PASS
ctest --test-dir cmake-build-release --output-on-failure -R for_unit_tests: PASS
python3 test.py: PASS
EOF

python3 scripts/issue_queue.py complete \
  --issue "$ISSUE_NAME" \
  --claim-id "$CLAIM_ID" \
  --owner controller/subagent-1 \
  --summary-file /tmp/task-summary.txt \
  --validation-file /tmp/task-validation.txt
```

`DONE` requires a result summary, validation results, `Progress %=100`, and a completion timestamp.

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
python3 scripts/issue_queue.py reclaim-stale --older-than-minutes 30
```

This only reclaims rows whose lease is already expired and whose last update is at least the specified age. Reclaimed rows return to `NOT_STARTED`, retain the incremented `Attempt`, and receive an audit note describing the previous owner and claim.

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
