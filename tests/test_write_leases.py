from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from scripts import issue_queue, write_leases

REPO_ROOT = Path(__file__).resolve().parent.parent


class WriteLeaseTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.store_path = self.temp_path / "write_leases.json"
        self.repo_root = self.temp_path / "repo"
        self.now = issue_queue.utcNow().replace(microsecond=0)
        for relative in (
            "CMakeLists.txt",
            "src/core/CSerialization.h",
            "src/core/CSerialization.cpp",
            "src/core/CCoreTypeRegistration.cpp",
            "src/object/CItem.h",
            "src/object/CItem.cpp",
            "src/object/CObjectTypeRegistration.cpp",
            "src/gui/CLayout.cpp",
            "src/gui/CLayout.h",
            "src/gui/CTextureCache.cpp",
            "src/gui/CTextureCache.h",
            "src/gui/CGuiTypeRegistration.cpp",
            "src/gui/CAnimationTypeRegistration.cpp",
            "res/maps/testmap/script.py",
            "res/maps/testmap/config.json",
            "res/maps/testmap/map.json",
            "res/maps/testmap/dialog.json",
            "res/maps/testmap/dialog2.json",
            "scripts/generate_screenshots.py",
            "screenshots/menu.png",
        ):
            target = self.repo_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("placeholder\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def request(self, claim_id: str, scope_by_source: dict[str, list[str]], owner: str | None = None) -> dict:
        return write_leases.buildLeaseRequest(
            controller_id="ctrl-test",
            owner=owner or f"controller/ctrl-test/{claim_id}",
            claim_id=claim_id,
            scope_by_source=scope_by_source,
            issue_name=f"[EPIC_01][STORY_01][SUBSTORY_01]Issue {claim_id}",
        )

    def acquire(self, claim_id: str, scope_by_source: dict[str, list[str]], now=None, owner: str | None = None):
        return write_leases.acquireLeases(
            self.store_path,
            [self.request(claim_id, scope_by_source, owner=owner)],
            now=now or self.now,
            repo_root=self.repo_root,
        )

    def storedLeases(self) -> list[dict]:
        return write_leases.loadStore(self.store_path)["leases"]

    def expandedPathsOf(self, payload: dict) -> set[str]:
        return {entry["path"] for entry in payload["acquired"][0]["scope"]["expanded"]}


class ScopeNormalizationTest(WriteLeaseTestBase):
    def test_normalization_cleans_separators_and_relative_prefixes(self) -> None:
        entries = write_leases.normalizeScope(
            [
                ("./src/object/CItem.cpp", write_leases.SOURCE_WORKER_DECLARED),
                ("src\\gui\\CLayout.cpp", write_leases.SOURCE_WORKER_DECLARED),
                ("res/maps/testmap//config.json", write_leases.SOURCE_WORKER_DECLARED),
            ],
            repo_root=self.repo_root,
        )
        self.assertEqual(
            ["res/maps/testmap/config.json", "src/gui/CLayout.cpp", "src/object/CItem.cpp"],
            [entry["path"] for entry in entries],
        )

    def test_existing_directories_normalize_to_prefix_scopes(self) -> None:
        entries = write_leases.normalizeScope(
            [("src/gui", write_leases.SOURCE_WORKBOOK_TARGET_FILES)], repo_root=self.repo_root
        )
        self.assertEqual(["src/gui/"], [entry["path"] for entry in entries])

    def test_duplicate_paths_keep_the_highest_confidence_source(self) -> None:
        entries = write_leases.normalizeScope(
            [
                ("src/object/CItem.cpp", write_leases.SOURCE_WORKBOOK_TARGET_FILES),
                ("src/object/CItem.cpp", write_leases.SOURCE_PR_CHANGED_FILES),
                ("src/object/CItem.cpp", write_leases.SOURCE_WORKER_DECLARED),
            ],
            repo_root=self.repo_root,
        )
        self.assertEqual(1, len(entries))
        self.assertEqual(write_leases.SOURCE_PR_CHANGED_FILES, entries[0]["source"])
        self.assertEqual(
            write_leases.SCOPE_SOURCE_CONFIDENCE[write_leases.SOURCE_PR_CHANGED_FILES], entries[0]["confidence"]
        )

    def test_paths_outside_the_repository_are_rejected(self) -> None:
        for invalid in ("../outside.cpp", "/etc/passwd", "C:/game/src", "", "."):
            with self.assertRaises(write_leases.WriteLeaseError):
                write_leases.normalizeScopePath(invalid, repo_root=self.repo_root)

    def test_unknown_scope_source_is_rejected(self) -> None:
        with self.assertRaises(write_leases.WriteLeaseError):
            write_leases.normalizeScope([("src/object/CItem.cpp", "guesswork")], repo_root=self.repo_root)


class ScopeExpansionTest(WriteLeaseTestBase):
    def expand(self, path: str, source: str = write_leases.SOURCE_WORKER_DECLARED) -> dict[str, dict]:
        entries = write_leases.normalizeScope([(path, source)], repo_root=self.repo_root)
        return {entry["path"]: entry for entry in write_leases.expandScope(entries, repo_root=self.repo_root)}

    def test_header_expands_to_its_implementation_pair(self) -> None:
        expanded = self.expand("src/object/CItem.h")
        self.assertIn("src/object/CItem.cpp", expanded)
        self.assertEqual(write_leases.RULE_HEADER_PAIR, expanded["src/object/CItem.cpp"]["rule"])
        self.assertEqual("src/object/CItem.h", expanded["src/object/CItem.cpp"]["expandedFrom"])
        # Existing sources do not drag in build/type registration.
        self.assertNotIn("CMakeLists.txt", expanded)
        self.assertNotIn("src/object/CObjectTypeRegistration.cpp", expanded)

    def test_new_engine_source_expands_to_registration_and_cmake(self) -> None:
        expanded = self.expand("src/object/CNewRelic.cpp")
        self.assertIn("src/object/CNewRelic.h", expanded)
        self.assertIn("CMakeLists.txt", expanded)
        self.assertIn("src/object/CObjectTypeRegistration.cpp", expanded)
        self.assertEqual(write_leases.RULE_CMAKE_REGISTRATION, expanded["CMakeLists.txt"]["rule"])
        self.assertEqual(
            write_leases.RULE_TYPE_REGISTRATION, expanded["src/object/CObjectTypeRegistration.cpp"]["rule"]
        )

    def test_map_content_expands_to_the_whole_map_bundle(self) -> None:
        expanded = self.expand("res/maps/testmap/dialog2.json")
        self.assertIn("res/maps/testmap/", expanded)
        self.assertEqual(write_leases.RULE_MAP_BUNDLE, expanded["res/maps/testmap/"]["rule"])
        bundle_paths = set(expanded)
        for member in ("res/maps/testmap/script.py", "res/maps/testmap/config.json", "res/maps/testmap/map.json"):
            self.assertTrue(any(write_leases.pathsOverlap(member, path) for path in bundle_paths), member)

    def test_serialization_pair_expansion(self) -> None:
        expanded = self.expand("src/core/CSerialization.h")
        self.assertIn("src/core/CSerialization.cpp", expanded)
        self.assertEqual(write_leases.RULE_SERIALIZATION_PAIR, expanded["src/core/CSerialization.cpp"]["rule"])

    def test_generated_resource_producer_expands_to_its_output(self) -> None:
        expanded = self.expand("scripts/generate_screenshots.py")
        self.assertIn("screenshots/", expanded)
        self.assertEqual(write_leases.RULE_GENERATED_RESOURCE, expanded["screenshots/"]["rule"])

    def test_expansion_inherits_source_confidence(self) -> None:
        expanded = self.expand("src/object/CItem.h", source=write_leases.SOURCE_PR_CHANGED_FILES)
        derived = expanded["src/object/CItem.cpp"]
        self.assertEqual(write_leases.SOURCE_PR_CHANGED_FILES, derived["source"])
        self.assertEqual(
            write_leases.SCOPE_SOURCE_CONFIDENCE[write_leases.SOURCE_PR_CHANGED_FILES], derived["confidence"]
        )


class LeaseLifecycleTest(WriteLeaseTestBase):
    def test_acquire_batch_rolls_back_atomically_on_partial_conflict(self) -> None:
        self.acquire("claim-a", {write_leases.SOURCE_WORKER_DECLARED: ["src/object/CItem.cpp"]})
        self.assertEqual(1, len(self.storedLeases()))
        before = self.store_path.read_bytes()
        batch = [
            # No conflict on its own.
            self.request("claim-b", {write_leases.SOURCE_WORKER_DECLARED: ["res/maps/testmap/config.json"]}),
            # Conflicts with claim-a through the header/implementation pair expansion.
            self.request("claim-c", {write_leases.SOURCE_WORKER_DECLARED: ["src/object/CItem.h"]}),
        ]
        with self.assertRaises(write_leases.WriteLeaseConflict) as raised:
            write_leases.acquireLeases(self.store_path, batch, now=self.now, repo_root=self.repo_root)
        self.assertEqual(1, len(raised.exception.conflicts))
        self.assertEqual(before, self.store_path.read_bytes(), "failed batch must leave the store unchanged")
        self.assertEqual(1, len(self.storedLeases()))

    def test_conflicts_inside_one_batch_also_roll_back(self) -> None:
        batch = [
            self.request("claim-a", {write_leases.SOURCE_WORKER_DECLARED: ["src/gui/CLayout.cpp"]}),
            self.request("claim-b", {write_leases.SOURCE_WORKER_DECLARED: ["src/gui/CLayout.h"]}),
        ]
        with self.assertRaises(write_leases.WriteLeaseConflict):
            write_leases.acquireLeases(self.store_path, batch, now=self.now, repo_root=self.repo_root)
        self.assertEqual([], self.storedLeases())

    def test_non_overlapping_writes_proceed_concurrently(self) -> None:
        first = self.acquire("claim-a", {write_leases.SOURCE_WORKER_DECLARED: ["src/gui/CLayout.cpp"]})
        second = self.acquire("claim-b", {write_leases.SOURCE_WORKER_DECLARED: ["src/gui/CTextureCache.cpp"]})
        self.assertEqual(write_leases.STATE_ACTIVE, first["acquired"][0]["state"])
        self.assertEqual(write_leases.STATE_ACTIVE, second["acquired"][0]["state"])
        self.assertEqual(2, len(self.storedLeases()))

    def test_renew_extends_expiry_and_is_all_or_nothing(self) -> None:
        payload = self.acquire("claim-a", {write_leases.SOURCE_WORKER_DECLARED: ["src/object/CItem.cpp"]})
        lease = payload["acquired"][0]
        later = self.now + timedelta(minutes=30)
        renewed = write_leases.renewLeases(
            self.store_path,
            [lease["leaseId"]],
            owner=lease["owner"],
            claim_id=lease["claimId"],
            extend_minutes=240,
            now=later,
        )
        self.assertEqual(issue_queue.formatUtc(later), renewed["renewed"][0]["renewedAtUtc"])
        self.assertEqual(issue_queue.formatUtc(later + timedelta(minutes=240)), renewed["renewed"][0]["expiresAtUtc"])
        before = self.store_path.read_bytes()
        with self.assertRaises(write_leases.WriteLeaseError):
            write_leases.renewLeases(
                self.store_path,
                [lease["leaseId"], "missing-lease-id"],
                owner=lease["owner"],
                claim_id=lease["claimId"],
                now=later,
            )
        self.assertEqual(before, self.store_path.read_bytes(), "failed renew batch must not change the store")

    def test_renew_requires_matching_owner_and_claim(self) -> None:
        lease = self.acquire("claim-a", {write_leases.SOURCE_WORKER_DECLARED: ["src/object/CItem.cpp"]})["acquired"][0]
        with self.assertRaises(write_leases.WriteLeaseError):
            write_leases.renewLeases(
                self.store_path,
                [lease["leaseId"]],
                owner="controller/other/subagent-9",
                claim_id=lease["claimId"],
                now=self.now,
            )

    def test_release_frees_the_scope_for_new_leases(self) -> None:
        lease = self.acquire("claim-a", {write_leases.SOURCE_WORKER_DECLARED: ["src/object/CItem.cpp"]})["acquired"][0]
        released = write_leases.releaseLeases(
            self.store_path, [lease["leaseId"]], owner=lease["owner"], claim_id=lease["claimId"], now=self.now
        )
        self.assertEqual(write_leases.STATE_RELEASED, released["released"][0]["state"])
        follow_up = self.acquire("claim-b", {write_leases.SOURCE_WORKER_DECLARED: ["src/object/CItem.h"]})
        self.assertEqual(write_leases.STATE_ACTIVE, follow_up["acquired"][0]["state"])

    def test_expired_leases_stop_blocking_but_cannot_renew(self) -> None:
        lease = self.acquire("claim-a", {write_leases.SOURCE_WORKER_DECLARED: ["src/object/CItem.cpp"]})["acquired"][0]
        after_expiry = self.now + timedelta(minutes=write_leases.DEFAULT_LEASE_MINUTES + 1)
        follow_up = self.acquire(
            "claim-b", {write_leases.SOURCE_WORKER_DECLARED: ["src/object/CItem.h"]}, now=after_expiry
        )
        self.assertEqual(write_leases.STATE_ACTIVE, follow_up["acquired"][0]["state"])
        with self.assertRaisesRegex(write_leases.WriteLeaseError, "expired"):
            write_leases.renewLeases(
                self.store_path,
                [lease["leaseId"]],
                owner=lease["owner"],
                claim_id=lease["claimId"],
                now=after_expiry,
            )

    def test_recovery_is_lease_lifecycle_only(self) -> None:
        workbook_sentinel = self.temp_path / "queue.xlsx"
        workbook_sentinel.write_bytes(b"canonical workbook bytes; write_leases must never touch them")
        workbook_before = workbook_sentinel.read_bytes()
        lease = self.acquire("claim-a", {write_leases.SOURCE_WORKER_DECLARED: ["src/object/CItem.cpp"]})["acquired"][0]
        with self.assertRaisesRegex(write_leases.WriteLeaseError, "still valid"):
            write_leases.recoverLeases(self.store_path, [lease["leaseId"]], reason="worker vanished", now=self.now)
        after_expiry = self.now + timedelta(minutes=write_leases.DEFAULT_LEASE_MINUTES + 1)
        recovered = write_leases.recoverLeases(
            self.store_path, [lease["leaseId"]], reason="worker vanished", now=after_expiry
        )
        self.assertEqual(write_leases.STATE_RECOVERED, recovered["recovered"][0]["state"])
        self.assertEqual("worker vanished", recovered["recovered"][0]["recoveryReason"])
        self.assertEqual(issue_queue.formatUtc(after_expiry), recovered["recovered"][0]["recoveredAtUtc"])
        self.assertEqual(workbook_before, workbook_sentinel.read_bytes())

    def test_listing_is_read_only_inspection_without_a_lease(self) -> None:
        self.acquire("claim-a", {write_leases.SOURCE_WORKER_DECLARED: ["src/object/CItem.cpp"]})
        before = self.store_path.read_bytes()
        listing = write_leases.listLeases(self.store_path, states={write_leases.STATE_ACTIVE}, now=self.now)
        self.assertEqual(1, listing["count"])
        self.assertEqual(before, self.store_path.read_bytes())

    def test_validate_flags_overlapping_active_scopes_and_expired_leases(self) -> None:
        self.acquire("claim-a", {write_leases.SOURCE_WORKER_DECLARED: ["src/object/CItem.cpp"]})
        store = write_leases.loadStore(self.store_path)
        duplicate = json.loads(json.dumps(store["leases"][0]))
        duplicate["leaseId"] = "duplicate-scope-lease"
        duplicate["claimId"] = "claim-b"
        store["leases"].append(duplicate)
        errors, warnings = write_leases.validateStore(store, now=self.now)
        self.assertTrue(any("overlapping ACTIVE" in error for error in errors), errors)
        errors, warnings = write_leases.validateStore(
            write_leases.loadStore(self.store_path), now=self.now + timedelta(minutes=500)
        )
        self.assertEqual([], errors)
        self.assertTrue(any("expired" in warning for warning in warnings), warnings)


class FalsePositiveTargetOverlapTest(WriteLeaseTestBase):
    def test_workbook_target_overlap_does_not_block_disjoint_write_scopes(self) -> None:
        shared_target = {write_leases.SOURCE_WORKBOOK_TARGET_FILES: ["src/gui"]}
        first = self.acquire("claim-a", {**shared_target, write_leases.SOURCE_WORKER_DECLARED: ["src/gui/CLayout.cpp"]})
        second = self.acquire(
            "claim-b", {**shared_target, write_leases.SOURCE_WORKER_DECLARED: ["src/gui/CTextureCache.cpp"]}
        )
        # Both leases record the overlapping workbook target with low confidence...
        for payload in (first, second):
            requested = payload["acquired"][0]["scope"]["requested"]
            self.assertIn("src/gui/", [entry["path"] for entry in requested])
        overlap = write_leases.scopeOverlaps(["src/gui/"], ["src/gui/"])
        self.assertTrue(overlap, "workbook targets do overlap; the lease layer must still allow both")
        # ...but the effective expanded write scopes are disjoint, so both leases are ACTIVE.
        self.assertEqual(write_leases.STATE_ACTIVE, first["acquired"][0]["state"])
        self.assertEqual(write_leases.STATE_ACTIVE, second["acquired"][0]["state"])
        self.assertEqual(
            [],
            write_leases.scopeOverlaps(
                self.expandedPathsOf(first) - {"src/gui/"}, self.expandedPathsOf(second) - {"src/gui/"}
            ),
        )

    def test_workbook_targets_still_guard_when_no_concrete_scope_exists(self) -> None:
        self.acquire("claim-a", {write_leases.SOURCE_WORKBOOK_TARGET_FILES: ["src/gui"]})
        with self.assertRaises(write_leases.WriteLeaseConflict):
            self.acquire("claim-b", {write_leases.SOURCE_WORKBOOK_TARGET_FILES: ["src/gui/CLayout.cpp"]})


class WriteLeaseCliTest(WriteLeaseTestBase):
    def runCli(self, *argv: str) -> tuple[int, dict]:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = write_leases.main(
                [argv[0], "--store", str(self.store_path), "--repo-root", str(self.repo_root), *argv[1:]]
            )
        text = stdout.getvalue()
        return code, json.loads(text) if text.strip() else {}

    def test_cli_acquire_list_conflict_and_validate(self) -> None:
        code, payload = self.runCli(
            "acquire",
            "--controller-id",
            "ctrl-test",
            "--owner",
            "controller/ctrl-test/subagent-1",
            "--claim-id",
            "claim-a",
            "--declared-file",
            "src/object/CItem.cpp",
        )
        self.assertEqual(0, code)
        self.assertEqual(1, len(payload["acquired"]))

        code, payload = self.runCli("list", "--state", "ACTIVE")
        self.assertEqual(0, code)
        self.assertEqual(1, payload["count"])

        code, payload = self.runCli(
            "acquire",
            "--controller-id",
            "ctrl-test",
            "--owner",
            "controller/ctrl-test/subagent-2",
            "--claim-id",
            "claim-b",
            "--declared-file",
            "src/object/CItem.h",
        )
        self.assertEqual(3, code, "conflicting acquire must exit with the conflict status")
        self.assertEqual([], payload["acquired"])
        self.assertTrue(payload["conflicts"])

        code, payload = self.runCli("validate")
        self.assertEqual(0, code)
        self.assertEqual([], payload["errors"])


class IssueQueueBehaviorUnchangedTest(unittest.TestCase):
    """The lease layer is additive: workbook queue semantics stay exactly as before."""

    def test_issue_queue_validate_passes_against_the_repo_workbooks(self) -> None:
        for workbook in (
            REPO_ROOT / "planning" / "fall_of_nouraajd_issue_proposals.xlsx",
            REPO_ROOT / "planning" / "fall_of_nouraajd_github_issues_implementation_workbook_migrated.xlsx",
        ):
            with self.subTest(workbook=workbook.name):
                self.assertTrue(workbook.is_file(), workbook)
                state = issue_queue.loadQueue(workbook)
                try:
                    errors, _ = issue_queue.validateQueueState(state)
                finally:
                    state.workbook.close()
                self.assertEqual([], errors)
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = issue_queue.main(["validate", "--workbook", str(workbook)])
                self.assertEqual(0, exit_code, stdout.getvalue())

    def test_issue_queue_module_does_not_depend_on_write_leases(self) -> None:
        source = (REPO_ROOT / "scripts" / "issue_queue.py").read_text(encoding="utf-8")
        self.assertNotIn("write_leases", source)

    def test_target_file_overlap_stays_advisory_for_queue_claims(self) -> None:
        # Reuse the canonical issue_queue fixture: issues B and D both target src/shared.cpp.
        from tests import test_issue_queue

        helper = test_issue_queue.IssueQueueTest("setUp")
        helper.setUp()
        try:
            first = issue_queue.claimTask(
                helper.workbook_path, owner="controller/ctrl-a/subagent-1", issueName=helper.issue_b, leaseMinutes=30
            )
            second = issue_queue.claimTask(
                helper.workbook_path, owner="controller/ctrl-b/subagent-1", issueName=helper.issue_d, leaseMinutes=30
            )
            self.assertTrue(first.get("claimed"))
            self.assertTrue(second.get("claimed"), "target-file overlap must stay advisory, not blocking")
        finally:
            helper.tearDown()


if __name__ == "__main__":
    unittest.main()
