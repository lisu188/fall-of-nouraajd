#!/usr/bin/env python3
"""Durable, read-only controller transition reconciler.

Controller state is spread across the XLSX queue row, claim IDs, worktrees,
branches, the implementation pull request, its CI, and the terminal workbook
pull request. After a restart a controller must decide what to do next WITHOUT
re-doing a transition it already performed (a duplicate claim, a duplicate
implementation PR, a duplicate terminal/DONE write).

This module derives a single deterministic controller state from a snapshot of
that evidence and returns the next action plus an idempotency key for the write
that action would perform. It is strictly read-only: it consumes a JSON evidence
blob and returns JSON. It never touches the workbook, git, or GitHub, so running
`snapshot`/`reconcile`/`next-action` can never itself duplicate a transition.

Correlation is by exact identity (claim ID, issue name, owner, branch, head SHA,
PR number). Title matching alone is never authoritative. When the evidence
contradicts itself the reconciler returns ``recovery_required`` with the
conflicting evidence rather than guessing a write.

Evidence schema (all fields optional unless noted; extra keys are ignored)::

    {
      "issueName": "[EPIC_..]..",          # required
      "owner": "controller/ctrl-x/subagent-1",
      "claimId": "abc-123",                # required for any write transition
      "queue": { "status": "IN_PROGRESS", "owner": "...", "claimId": "...",
                 "issueName": "...", "stale": false },
      "implementationPr": { "number": 12, "claimId": "...", "issueName": "...",
                 "owner": "...", "headSha": "...", "branch": "...",
                 "merged": false, "mergeableState": "clean",
                 "statusCheckRollup": [ ... ] },   # normalized by pr_review_audit
      "terminalPr": { "number": 13, "claimId": "...", "merged": false },
      "worktreeReady": true,               # local evidence (subagent registry)
      "workerRunning": true
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Any, Sequence

try:
    import pr_review_audit as audit
except ImportError:  # pragma: no cover - used when imported as scripts.controller_reconciler
    from scripts import pr_review_audit as audit

# Controller lifecycle states (durable evidence only; worktree/worker states are
# supplied as local evidence by the subagent registry, not inferred here).
STATE_CLAIM_SELECTED = "claim_selected"
STATE_WORKTREE_READY = "worktree_ready"
STATE_WORKER_RUNNING = "worker_running"
STATE_IMPLEMENTATION_PR_OPEN = "implementation_pr_open"
STATE_CI_PENDING = "ci_pending"
STATE_CI_PASSED = "ci_passed"
STATE_CI_FAILED = "ci_failed"
STATE_IMPLEMENTATION_MERGED = "implementation_merged"
STATE_TERMINAL_PR_OPEN = "terminal_pr_open"
STATE_DONE = "done"
STATE_BLOCKED = "blocked"
STATE_RECOVERY_REQUIRED = "recovery_required"

# Deterministic next actions. Each maps to exactly one write a controller would
# perform; NONE / WAIT_FOR_CI / RECOVERY_REQUIRED perform no write.
ACTION_NONE = "none"
ACTION_CREATE_WORKTREE = "create_worktree"
ACTION_RUN_WORKER = "run_worker"
ACTION_OPEN_IMPLEMENTATION_PR = "open_implementation_pr"
ACTION_WAIT_FOR_CI = "wait_for_ci"
ACTION_FIX_CI = "fix_ci"
ACTION_MERGE_IMPLEMENTATION = "merge_implementation"
ACTION_MARK_DONE = "mark_done"
ACTION_RECLAIM_OR_RECOVER = "reclaim_or_recover"
ACTION_RECOVERY_REQUIRED = "recovery_required"

# Actions that perform a durable write and therefore carry an idempotency key.
_WRITE_ACTIONS = frozenset(
    {
        ACTION_CREATE_WORKTREE,
        ACTION_RUN_WORKER,
        ACTION_OPEN_IMPLEMENTATION_PR,
        ACTION_MERGE_IMPLEMENTATION,
        ACTION_MARK_DONE,
    }
)


class ReconcilerError(RuntimeError):
    pass


@dataclass(frozen=True)
class ControllerSnapshot:
    issueName: str
    claimId: str
    owner: str
    state: str
    nextAction: str
    idempotencyKey: str | None
    contradictions: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    def toPayload(self) -> dict[str, Any]:
        return {
            "issueName": self.issueName,
            "claimId": self.claimId,
            "owner": self.owner,
            "state": self.state,
            "nextAction": self.nextAction,
            "idempotencyKey": self.idempotencyKey,
            "contradictions": list(self.contradictions),
            "evidence": list(self.evidence),
        }


@dataclass
class _Facts:
    issueName: str
    claimId: str
    owner: str
    queue: dict[str, Any]
    implementationPr: dict[str, Any] | None
    terminalPr: dict[str, Any] | None
    worktreeReady: bool
    workerRunning: bool
    contradictions: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


def idempotencyKey(claimId: str, transition: str) -> str:
    """Stable key for a write transition: exact claim ID + transition type.

    Re-deriving the same state after a restart yields the same key, so a caller
    that records applied keys can skip a transition it already performed.
    """
    if not claimId:
        raise ReconcilerError("idempotency key requires a non-empty claim id")
    return f"{claimId}:{transition}"


def _asDict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _str(value: Any) -> str:
    return str(value or "").strip()


def _prField(record: dict[str, Any], *names: str) -> Any:
    return audit.firstValue(record, *names, default=None)


def _mismatch(facts: _Facts, label: str, expected: str, actual: str) -> None:
    if expected and actual and expected != actual:
        facts.contradictions.append(f"{label} mismatch: expected {expected!r}, saw {actual!r}")


def _correlatePr(facts: _Facts, record: dict[str, Any], role: str) -> None:
    """Verify a PR record belongs to this claim/issue/owner by exact identity."""
    prClaim = _str(_prField(record, "claimId", "claim_id"))
    prIssue = _str(_prField(record, "issueName", "issue", "linkedIssue"))
    prOwner = _str(_prField(record, "owner", "author"))
    _mismatch(facts, f"{role} PR claim id", facts.claimId, prClaim)
    _mismatch(facts, f"{role} PR issue name", facts.issueName, prIssue)
    # Owner is advisory (a PR may be opened by a bot account); only flag when the
    # PR explicitly records a controller owner that differs from this claim's.
    if prOwner.startswith("controller/"):
        _mismatch(facts, f"{role} PR owner", facts.owner, prOwner)


def _ciState(record: dict[str, Any]) -> audit.CheckSummary:
    return audit.checkSummary(record)


def buildFacts(evidence: dict[str, Any]) -> _Facts:
    if not isinstance(evidence, dict):
        raise ReconcilerError("evidence must be a JSON object")
    issueName = _str(evidence.get("issueName"))
    if not issueName:
        raise ReconcilerError("evidence.issueName is required")
    queue = _asDict(evidence.get("queue"))
    claimId = _str(evidence.get("claimId")) or _str(audit.firstValue(queue, "claimId", "claim_id", default=""))
    owner = _str(evidence.get("owner")) or audit.queueOwner(queue)
    impl = evidence.get("implementationPr")
    term = evidence.get("terminalPr")
    facts = _Facts(
        issueName=issueName,
        claimId=claimId,
        owner=owner,
        queue=queue,
        implementationPr=impl if isinstance(impl, dict) else None,
        terminalPr=term if isinstance(term, dict) else None,
        worktreeReady=audit.truthy(evidence.get("worktreeReady")),
        workerRunning=audit.truthy(evidence.get("workerRunning")),
    )

    # Queue row must describe this issue; a row for a different issue is a
    # correlation error, not a guessable transition.
    queueIssue = _str(audit.firstValue(queue, "issueName", "issue", default=""))
    _mismatch(facts, "queue issue name", issueName, queueIssue)
    queueClaim = _str(audit.firstValue(queue, "claimId", "claim_id", default=""))
    if claimId and queueClaim:
        _mismatch(facts, "queue claim id", claimId, queueClaim)

    if facts.implementationPr is not None:
        _correlatePr(facts, facts.implementationPr, "implementation")
    if facts.terminalPr is not None:
        _correlatePr(facts, facts.terminalPr, "terminal")
    return facts


def _deriveState(facts: _Facts) -> str:
    queueStatus = audit.queueStatus(facts.queue)
    implMerged = facts.implementationPr is not None and audit.truthy(
        audit.firstValue(facts.implementationPr, "merged", default=False)
    )

    # Contradiction: implementation merged but the queue row was never claimed.
    if implMerged and queueStatus in {"not_started", ""}:
        facts.contradictions.append("implementation PR merged but queue row is not claimed")
    # Contradiction: queue marked DONE while an implementation PR is still open.
    if queueStatus == "done" and facts.implementationPr is not None and not implMerged:
        facts.contradictions.append("queue row is DONE but implementation PR is still open")

    if facts.contradictions:
        return STATE_RECOVERY_REQUIRED

    if queueStatus == "done":
        return STATE_DONE
    if queueStatus == "blocked":
        return STATE_BLOCKED

    if facts.implementationPr is not None:
        if implMerged:
            # Merged implementation but the row isn't DONE yet -> terminal/DONE
            # reconciliation is what remains.
            if facts.terminalPr is not None and not audit.truthy(
                audit.firstValue(facts.terminalPr, "merged", default=False)
            ):
                return STATE_TERMINAL_PR_OPEN
            return STATE_IMPLEMENTATION_MERGED
        ci = _ciState(facts.implementationPr)
        if ci.ambiguous:
            facts.contradictions.append(f"ambiguous CI identity: {', '.join(ci.ambiguous)}")
            return STATE_RECOVERY_REQUIRED
        if ci.state == "failure":
            return STATE_CI_FAILED
        if ci.state in {"pending", "unknown"}:
            return STATE_CI_PENDING
        if ci.state == "success":
            return STATE_CI_PASSED
        return STATE_IMPLEMENTATION_PR_OPEN

    # No implementation PR yet: decide by claim / local evidence.
    if audit.queueClaimIsStale(facts.queue):
        return STATE_RECOVERY_REQUIRED
    if facts.workerRunning:
        return STATE_WORKER_RUNNING
    if facts.worktreeReady:
        return STATE_WORKTREE_READY
    if queueStatus == "in_progress":
        return STATE_CLAIM_SELECTED
    # No claim, no PR, no local evidence: nothing selected for this issue.
    return STATE_CLAIM_SELECTED


def _nextAction(state: str, facts: _Facts) -> str:
    if state == STATE_RECOVERY_REQUIRED:
        return ACTION_RECOVERY_REQUIRED
    if state == STATE_DONE:
        return ACTION_NONE
    if state == STATE_BLOCKED:
        return ACTION_NONE
    if state == STATE_CLAIM_SELECTED:
        return ACTION_CREATE_WORKTREE
    if state == STATE_WORKTREE_READY:
        return ACTION_RUN_WORKER
    if state == STATE_WORKER_RUNNING:
        return ACTION_OPEN_IMPLEMENTATION_PR
    if state == STATE_CI_PENDING or state == STATE_IMPLEMENTATION_PR_OPEN:
        return ACTION_WAIT_FOR_CI
    if state == STATE_CI_FAILED:
        return ACTION_FIX_CI
    if state == STATE_CI_PASSED:
        # Only merge when the PR is actually mergeable; a dirty/blocked state is
        # not a merge signal.
        merge = audit.mergeState(facts.implementationPr or {})
        if merge in {"dirty", "blocked", "behind"}:
            return ACTION_FIX_CI
        return ACTION_MERGE_IMPLEMENTATION
    if state == STATE_IMPLEMENTATION_MERGED:
        return ACTION_MARK_DONE
    if state == STATE_TERMINAL_PR_OPEN:
        return ACTION_WAIT_FOR_CI
    return ACTION_NONE


def reconcile(evidence: dict[str, Any]) -> ControllerSnapshot:
    facts = buildFacts(evidence)
    state = _deriveState(facts)
    action = _nextAction(state, facts)
    key: str | None = None
    if action in _WRITE_ACTIONS:
        if not facts.claimId:
            # A write transition without a claim id cannot be made idempotent, so
            # refuse to recommend it rather than risk a duplicate.
            facts.contradictions.append(f"action {action} requires a claim id for idempotency")
            state = STATE_RECOVERY_REQUIRED
            action = ACTION_RECOVERY_REQUIRED
        else:
            key = idempotencyKey(facts.claimId, action)
    return ControllerSnapshot(
        issueName=facts.issueName,
        claimId=facts.claimId,
        owner=facts.owner,
        state=state,
        nextAction=action,
        idempotencyKey=key,
        contradictions=tuple(facts.contradictions),
        evidence=tuple(facts.evidence),
    )


def snapshot(evidence: dict[str, Any]) -> ControllerSnapshot:
    """Alias for reconcile(): both derive the read-only snapshot deterministically."""
    return reconcile(evidence)


def _loadEvidence(path: str | None) -> dict[str, Any]:
    if path and path != "-":
        with open(path, encoding="utf-8") as handle:
            raw = handle.read()
    else:
        raw = sys.stdin.read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReconcilerError(f"evidence is not valid JSON: {exc}") from exc


def parseArgs(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("snapshot", "reconcile", "next-action"):
        p = sub.add_parser(name, help=f"Read-only {name} over a controller evidence blob.")
        p.add_argument("--evidence-file", help="Path to a JSON evidence blob; '-' or omitted reads stdin.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parseArgs(sys.argv[1:] if argv is None else argv)
    try:
        evidence = _loadEvidence(args.evidence_file)
        result = reconcile(evidence)
    except ReconcilerError as exc:
        print(f"controller_reconciler: {exc}", file=sys.stderr)
        return 2
    if args.command == "next-action":
        payload: dict[str, Any] = {"nextAction": result.nextAction, "idempotencyKey": result.idempotencyKey}
    else:
        payload = result.toPayload()
    print(json.dumps(payload, indent=2, sort_keys=True))
    # A required recovery is a non-zero, non-crash signal so callers can branch.
    return 1 if result.state == STATE_RECOVERY_REQUIRED else 0


if __name__ == "__main__":
    raise SystemExit(main())
