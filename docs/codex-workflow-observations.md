# Codex workflow observation ledger

The workflow observation ledger records durable evidence about controller, optimizer, CI, PR, resource, recovery, and
prompt problems. It is not a second implementation backlog. The canonical implementation queue remains
`planning/fall_of_nouraajd_issue_proposals.xlsx`; observations are workflow leads that later optimizers must validate,
rank, reproduce, fix, and close.

## Storage model

Records are immutable JSON files under:

```text
planning/workflow_observations/records/<observation-id>.json
```

Resolution receipts are immutable JSON files under:

```text
planning/workflow_observations/resolutions/<observation-id>.json
```

There is one observation per file and one optional receipt per observation. Filenames must match the record or receipt
ID. The CLI writes canonical UTF-8 JSON with sorted keys, two-space indentation, and one trailing newline. It creates the
directories on first write. Read-only commands do not create directories.

Do not edit or delete existing records or receipts. If an observation is fixed, duplicated, invalid, or intentionally not
fixed, add a receipt. Keep every occurrence of a repeated problem; recurrence is derived by grouping normalized
fingerprints without discarding evidence.

## CLI

Use the standard-library CLI:

```bash
python3 scripts/workflow_observations.py validate
python3 scripts/workflow_observations.py validate --base origin/main
python3 scripts/workflow_observations.py list --state open
python3 scripts/workflow_observations.py show --id <OBSERVATION_ID>
python3 scripts/workflow_observations.py next
```

Create an observation after evidence and secret review:

```bash
python3 scripts/workflow_observations.py record \
  --controller-id "$CONTROLLER_ID" \
  --role controller \
  --category ci \
  --severity medium \
  --phase validation \
  --summary "Linux CI failure was rediscovered without durable evidence" \
  --details-file /tmp/observation-details.txt \
  --impact "Controllers spent time repeating the same CI triage" \
  --evidence-file /tmp/observation-evidence.json \
  --affected-path .github/workflows/build.yml \
  --fingerprint "linux ci rediscovery without durable evidence"
```

Resolve after the fixing implementation PR has merged and post-merge verification has passed:

```bash
python3 scripts/workflow_observations.py resolve \
  --id "$OBSERVATION_ID" \
  --status resolved \
  --resolver "$CONTROLLER_ID" \
  --summary-file /tmp/resolution-summary.txt \
  --evidence-file /tmp/resolution-evidence.json \
  --merged-pr "$PR_NUMBER" \
  --merge-commit "$MERGE_COMMIT"
```

Supported observation categories are `queue_lease`, `subagent_status`, `git_worktrees`, `prs`, `ci`, `resources`,
`recovery`, `prompt_drift`, `observability`, and `other`. Severities are `critical`, `high`, `medium`, and `low`.
Resolution statuses are `resolved`, `duplicate`, `invalid`, and `wont-fix`.

## Workflow rules

Workers, QA, and project-manager agents report observations to the controller. They do not publish ledger files
themselves. Record workflow failures and optimization leads, not gameplay defects and not routine progress.

Record observations for significant queue or lease faults, stale state, PR or merge failures, CI waste, prompt drift,
resource or recovery failures, missing worker status, unsafe ambiguity, and repeated manual intervention. Include
bounded evidence, affected repo-relative paths, impact, and a normalized recurrence fingerprint. Never store secrets,
environment dumps, private keys, access tokens, or oversized logs.

Publish observation files through observation-only pull requests after evidence and secret review:

- record-only PRs add only files under `planning/workflow_observations/records/`;
- resolution-only PRs add only files under `planning/workflow_observations/resolutions/`;
- never mix ledger files with XLSX, implementation, or workflow-code changes;
- run `python3 scripts/workflow_observations.py validate` before publication;
- on pull requests, run `python3 scripts/workflow_observations.py validate --base <base-ref>` to reject edits or
  deletions of immutable records and receipts;
- same-ID publication fails because files are created with exclusive no-overwrite semantics.

Observation-only and resolution-only PRs are not CI-exempt under the current repository policy. They do not need global
serialization because each record or receipt has a distinct immutable path, but branch protection and the normal PR merge
policy still apply unless the repository owner adds an explicit exemption later.

At each optimizer cycle, validate the ledger and review open observations before selecting new workflow work. Use
`next` as deterministic evidence, not as an automatic claim. The optimizer must still inspect current source, reproduce
or verify the root cause, check open workflow PRs, and choose a tested fix. Reference selected observation IDs in branch
names, commit or PR text where practical. After the fix merges and post-merge verification passes, publish a separate
resolution-only receipt PR.

Controller live status should include pending observation IDs when a workflow problem has been recorded locally or is
awaiting an observation-only or resolution-only PR.
