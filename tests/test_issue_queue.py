from __future__ import annotations

import contextlib
import io
import json
import multiprocessing
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET
from datetime import timedelta
from pathlib import Path

from scripts import issue_queue

CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def claim_worker(workbook_path: str, owner: str, output: multiprocessing.Queue) -> None:
    try:
        result = issue_queue.claimTask(Path(workbook_path), owner=owner, leaseMinutes=30)
        output.put(("ok", result.get("Issue Name"), result.get("claimId")))
    except Exception as exc:  # pragma: no cover - returned to parent for assertion
        output.put(("error", type(exc).__name__, str(exc)))


class IssueQueueTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workbook_path = Path(self.temp_dir.name) / "issues.xlsx"
        self.issue_a = "[EPIC_01][STORY_01][SUBSTORY_01]Low priority independent"
        self.issue_b = "[EPIC_01][STORY_01][SUBSTORY_02]Highest priority independent"
        self.issue_c = "[EPIC_01][STORY_01][SUBSTORY_03]Depends on highest priority"
        self.issue_d = "[EPIC_01][STORY_01][SUBSTORY_04]Overlaps active file"
        self.create_workbook(
            [
                self.task_row(self.issue_a, "P1", None, "src/a.cpp"),
                self.task_row(self.issue_b, "P0", None, "src/shared.cpp"),
                self.task_row(self.issue_c, "P0", self.issue_b, "src/c.cpp"),
                self.task_row(self.issue_d, "P0", None, "src/shared.cpp"),
            ]
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def task_row(self, issue_name: str, priority: str, dependencies: str | None, target_files: str) -> list[object]:
        base = {
            "Issue Name": issue_name,
            "Epic #": "EPIC_01",
            "Epic Title": "Test Epic",
            "Story #": "STORY_01",
            "Story Title": "Test Story",
            "Substory #": issue_name.split("[SUBSTORY_", 1)[1].split("]", 1)[0],
            "Substory Title": issue_name.split("]", 3)[-1],
            "Priority": priority,
            "Issue Type": "Test",
            "Component": "Tests",
            "Dependencies": dependencies,
            "Target Files / Modules": target_files,
            "Technical Code-Level Description": "Implement a deterministic test change.",
            "Acceptance Criteria": "The focused regression passes.",
            "Validation / Tests": "python3 -m unittest tests.test_issue_queue",
            "Source URLs": "https://github.com/lisu188/fall-of-nouraajd",
            "Status": issue_queue.STATUS_NOT_STARTED,
            "Owner": None,
            "Sprint": None,
            "Claim ID": None,
            "Claimed At UTC": None,
            "Updated At UTC": None,
            "Lease Until UTC": None,
            "Completed At UTC": None,
            "Progress %": 0,
            "Last Note": None,
            "Result Summary": None,
            "Validation Results": None,
            "Attempt": 0,
        }
        return [base[header] for header in issue_queue.ALL_HEADERS]

    def with_values(self, row: list[object], updates: dict[str, object]) -> list[object]:
        indexes = {header: index for index, header in enumerate(issue_queue.ALL_HEADERS)}
        for header, value in updates.items():
            row[indexes[header]] = value
        return row

    def create_workbook(self, rows: list[list[object]]) -> None:
        main_ns = issue_queue.MAIN_NS
        ET.register_namespace("x", main_ns)
        ET.register_namespace("r", OFFICE_REL_NS)

        worksheet = ET.Element(f"{{{main_ns}}}worksheet")
        dimension = ET.SubElement(worksheet, f"{{{main_ns}}}dimension")
        dimension.set(
            "ref",
            f"A1:{issue_queue.columnIndexToName(len(issue_queue.ALL_HEADERS))}{len(rows) + 1}",
        )
        sheet_data = ET.SubElement(worksheet, f"{{{main_ns}}}sheetData")
        self.append_xml_row(sheet_data, 1, list(issue_queue.ALL_HEADERS))
        for row_number, values in enumerate(rows, start=2):
            self.append_xml_row(sheet_data, row_number, values)

        workbook = ET.Element(f"{{{main_ns}}}workbook")
        sheets = ET.SubElement(workbook, f"{{{main_ns}}}sheets")
        sheet = ET.SubElement(sheets, f"{{{main_ns}}}sheet")
        sheet.set("name", issue_queue.ISSUE_SHEET)
        sheet.set("sheetId", "1")
        sheet.set(f"{{{OFFICE_REL_NS}}}id", "rId1")

        workbook_rels = ET.Element(f"{{{PACKAGE_REL_NS}}}Relationships")
        worksheet_rel = ET.SubElement(workbook_rels, f"{{{PACKAGE_REL_NS}}}Relationship")
        worksheet_rel.set("Id", "rId1")
        worksheet_rel.set(
            "Type",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet",
        )
        worksheet_rel.set("Target", "worksheets/sheet1.xml")
        styles_rel = ET.SubElement(workbook_rels, f"{{{PACKAGE_REL_NS}}}Relationship")
        styles_rel.set("Id", "rId2")
        styles_rel.set(
            "Type",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles",
        )
        styles_rel.set("Target", "styles.xml")

        root_rels = ET.Element(f"{{{PACKAGE_REL_NS}}}Relationships")
        office_rel = ET.SubElement(root_rels, f"{{{PACKAGE_REL_NS}}}Relationship")
        office_rel.set("Id", "rId1")
        office_rel.set(
            "Type",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
        )
        office_rel.set("Target", "xl/workbook.xml")

        content_types = ET.Element(f"{{{CONTENT_TYPES_NS}}}Types")
        for extension, content_type in (
            ("rels", "application/vnd.openxmlformats-package.relationships+xml"),
            ("xml", "application/xml"),
        ):
            default = ET.SubElement(content_types, f"{{{CONTENT_TYPES_NS}}}Default")
            default.set("Extension", extension)
            default.set("ContentType", content_type)
        for part_name, content_type in (
            ("/xl/workbook.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"),
            ("/xl/worksheets/sheet1.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"),
            ("/xl/styles.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"),
        ):
            override = ET.SubElement(content_types, f"{{{CONTENT_TYPES_NS}}}Override")
            override.set("PartName", part_name)
            override.set("ContentType", content_type)

        styles = ET.Element(f"{{{main_ns}}}styleSheet")
        fonts = ET.SubElement(styles, f"{{{main_ns}}}fonts", {"count": "1"})
        ET.SubElement(fonts, f"{{{main_ns}}}font")
        fills = ET.SubElement(styles, f"{{{main_ns}}}fills", {"count": "1"})
        fill = ET.SubElement(fills, f"{{{main_ns}}}fill")
        ET.SubElement(fill, f"{{{main_ns}}}patternFill", {"patternType": "none"})
        borders = ET.SubElement(styles, f"{{{main_ns}}}borders", {"count": "1"})
        ET.SubElement(borders, f"{{{main_ns}}}border")
        cell_style_xfs = ET.SubElement(styles, f"{{{main_ns}}}cellStyleXfs", {"count": "1"})
        ET.SubElement(
            cell_style_xfs,
            f"{{{main_ns}}}xf",
            {"numFmtId": "0", "fontId": "0", "fillId": "0", "borderId": "0"},
        )
        cell_xfs = ET.SubElement(styles, f"{{{main_ns}}}cellXfs", {"count": "1"})
        ET.SubElement(
            cell_xfs,
            f"{{{main_ns}}}xf",
            {"numFmtId": "0", "fontId": "0", "fillId": "0", "borderId": "0", "xfId": "0"},
        )

        with zipfile.ZipFile(self.workbook_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", self.xml_bytes(content_types))
            archive.writestr("_rels/.rels", self.xml_bytes(root_rels))
            archive.writestr("xl/workbook.xml", self.xml_bytes(workbook))
            archive.writestr("xl/_rels/workbook.xml.rels", self.xml_bytes(workbook_rels))
            archive.writestr("xl/worksheets/sheet1.xml", self.xml_bytes(worksheet))
            archive.writestr("xl/styles.xml", self.xml_bytes(styles))

    def append_xml_row(self, sheet_data: ET.Element, row_number: int, values: list[object]) -> None:
        row = ET.SubElement(sheet_data, issue_queue.xmlName("row"), {"r": str(row_number)})
        for column, value in enumerate(values, start=1):
            cell = ET.SubElement(
                row,
                issue_queue.xmlName("c"),
                {"r": f"{issue_queue.columnIndexToName(column)}{row_number}"},
            )
            if value is None:
                continue
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                cell.set("t", "n")
            else:
                cell.set("t", "str")
            value_node = ET.SubElement(cell, issue_queue.xmlName("v"))
            value_node.text = str(value)

    @staticmethod
    def xml_bytes(element: ET.Element) -> bytes:
        return ET.tostring(element, encoding="utf-8", xml_declaration=True)

    def set_claim_times(
        self,
        issue_name: str,
        *,
        lease_minutes_from_now: int | None,
        updated_minutes_ago: int | None = None,
    ) -> None:
        document = issue_queue.XlsxDocument.load(self.workbook_path)
        state = issue_queue.loadQueue(self.workbook_path)
        task = issue_queue.taskByName(state, issue_name)
        if lease_minutes_from_now is None:
            document.setCell(task.row, state.headers["Lease Until UTC"], None)
        else:
            lease = issue_queue.formatUtc(issue_queue.utcNow() + timedelta(minutes=lease_minutes_from_now))
            document.setCell(task.row, state.headers["Lease Until UTC"], lease)
        if updated_minutes_ago is not None:
            updated = issue_queue.formatUtc(issue_queue.utcNow() - timedelta(minutes=updated_minutes_ago))
            document.setCell(task.row, state.headers["Updated At UTC"], updated)
        document.save(self.workbook_path)

    def test_claim_respects_priority_dependency_and_active_file_overlap(self) -> None:
        first = issue_queue.claimTask(self.workbook_path, owner="controller/subagent-1")
        self.assertEqual(self.issue_b, first["Issue Name"])

        second = issue_queue.claimTask(self.workbook_path, owner="controller/subagent-2")
        self.assertEqual(self.issue_a, second["Issue Name"])

        state = issue_queue.loadQueue(self.workbook_path)
        eligible, rejected = issue_queue.eligibleTasks(state)
        self.assertEqual([], eligible)
        self.assertIn("dependencies-not-done", rejected[self.issue_c][0])
        self.assertTrue(any(reason.startswith("active-file-overlap") for reason in rejected[self.issue_d]))

    def test_shortlist_groups_highest_priority_and_selects_seeded_issue(self) -> None:
        first_story = "[EPIC_01][STORY_01][SUBSTORY_01]First high priority story"
        second_story = "[EPIC_01][STORY_02][SUBSTORY_01]Second high priority story"
        low_priority = "[EPIC_01][STORY_03][SUBSTORY_01]Lower priority story"
        blocked = "[EPIC_01][STORY_04][SUBSTORY_01]Blocked high priority story"
        self.create_workbook(
            [
                self.task_row(first_story, "P0", None, "src/first.cpp"),
                self.with_values(
                    self.task_row(second_story, "P0", None, "src/second.cpp"),
                    {"Story #": "STORY_02", "Story Title": "Second Story"},
                ),
                self.with_values(
                    self.task_row(low_priority, "P1", None, "src/low.cpp"),
                    {"Story #": "STORY_03", "Story Title": "Low Story"},
                ),
                self.with_values(
                    self.task_row(blocked, "P0", first_story, "src/blocked.cpp"),
                    {"Story #": "STORY_04", "Story Title": "Blocked Story"},
                ),
            ]
        )
        state = issue_queue.loadQueue(self.workbook_path)

        payload = issue_queue.shortlistTasks(state, seed="demo-seed", includeRejected=True)
        repeated = issue_queue.shortlistTasks(state, seed="demo-seed", includeRejected=True)

        self.assertTrue(payload["eligible"])
        self.assertEqual("P0", payload["highestPriority"])
        self.assertEqual(3, payload["eligibleCount"])
        self.assertEqual(2, payload["highestPriorityEligibleCount"])
        self.assertEqual(["STORY_01", "STORY_02"], [group["story"] for group in payload["storyGroups"]])
        self.assertEqual("EPIC_01/STORY_01", payload["selected"]["storyKey"])
        self.assertEqual(payload["selected"], repeated["selected"])
        self.assertIn(payload["selected"]["issue"]["issueName"], {first_story, second_story})
        story_two_payload = issue_queue.shortlistTasks(state, seed="story-two")
        self.assertEqual("EPIC_01/STORY_02", story_two_payload["selected"]["storyKey"])
        self.assertEqual(second_story, story_two_payload["selected"]["issue"]["issueName"])
        allow_overlap_payload = issue_queue.shortlistTasks(state, seed="demo-seed", allowFileOverlap=True)
        self.assertTrue(allow_overlap_payload["allowFileOverlap"])
        self.assertIn(
            "direct target-file overlap allowed by --allow-file-overlap",
            allow_overlap_payload["mechanicalFilters"],
        )
        self.assertNotIn(
            "direct target-file overlap excluded unless --allow-file-overlap is used",
            allow_overlap_payload["mechanicalFilters"],
        )
        self.assertIn(blocked, payload["rejected"])
        self.assertEqual(1, payload["rejectionSummary"]["dependencies-not-done"])

    def test_shortlist_cli_reports_without_mutating_workbook(self) -> None:
        before = self.workbook_path.read_bytes()
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = issue_queue.main(
                [
                    "shortlist",
                    "--workbook",
                    str(self.workbook_path),
                    "--seed",
                    "demo-seed",
                    "--include-rejected",
                    "--json",
                ]
            )
        payload = json.loads(stdout.getvalue())

        self.assertEqual(0, exit_code)
        self.assertEqual(before, self.workbook_path.read_bytes())
        self.assertEqual("demo-seed", payload["selectionSeed"])
        self.assertTrue(payload["eligible"])
        self.assertEqual("P0", payload["highestPriority"])
        self.assertFalse(payload["allowFileOverlap"])
        self.assertEqual(0, payload["activeCount"])
        self.assertEqual(0, payload["unexpiredActiveCount"])
        self.assertEqual(0, payload["staleClaimCount"])
        self.assertEqual({"total": 0, "unexpired": 0, "stale": 0}, payload["activeClaims"])
        self.assertIn(
            "direct target-file overlap excluded unless --allow-file-overlap is used",
            payload["mechanicalFilters"],
        )
        self.assertIn("storyGroups", payload)
        self.assertIn("rejected", payload)

    def test_shortlist_reports_unexpired_and_stale_active_counts(self) -> None:
        expired = issue_queue.claimTask(self.workbook_path, owner="controller/subagent-1", leaseMinutes=1)
        self.set_claim_times(expired["Issue Name"], lease_minutes_from_now=-10, updated_minutes_ago=10)
        unexpired = issue_queue.claimTask(self.workbook_path, owner="controller/subagent-2", leaseMinutes=30)
        state = issue_queue.loadQueue(self.workbook_path)

        payload = issue_queue.shortlistTasks(state, seed="active-counts")

        self.assertEqual(2, payload["activeCount"])
        self.assertEqual(1, payload["unexpiredActiveCount"])
        self.assertEqual(1, payload["staleClaimCount"])
        self.assertEqual({"total": 2, "unexpired": 1, "stale": 1}, payload["activeClaims"])
        self.assertEqual([expired["Issue Name"]], [item["issueName"] for item in payload["staleClaims"]])
        self.assertNotIn(unexpired["Issue Name"], [item["issueName"] for item in payload["staleClaims"]])

    def test_controller_id_generates_unique_owner_prefix(self) -> None:
        first = issue_queue.generateControllerId(hostname="Build Host.local", pid=1234, unique="ABCDEF12")
        second = issue_queue.generateControllerId(hostname="Build Host.local", pid=1234, unique="98765432")

        self.assertEqual("ctrl-build-host-1234-abcdef12", first)
        self.assertEqual("ctrl-build-host-1234-98765432", second)
        self.assertNotEqual(first, second)
        self.assertEqual("controller/ctrl-build-host-1234-abcdef12", issue_queue.controllerOwnerPrefix(first))
        self.assertEqual(
            "controller/ctrl-build-host-1234-abcdef12/subagent-1",
            issue_queue.controllerOwner(first, "Subagent 1"),
        )

    def test_controller_id_cli_prints_owner_prefix_without_workbook(self) -> None:
        missing_workbook = Path(self.temp_dir.name) / "missing.xlsx"
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = issue_queue.main(
                [
                    "controller-id",
                    "--controller-id",
                    "ctrl-demo-1",
                    "--worker",
                    "QA Agent",
                    "--workbook",
                    str(missing_workbook),
                ]
            )
        payload = json.loads(stdout.getvalue())

        self.assertEqual(0, exit_code)
        self.assertEqual("ctrl-demo-1", payload["controllerId"])
        self.assertEqual("controller/ctrl-demo-1", payload["ownerPrefix"])
        self.assertEqual("controller/ctrl-demo-1/qa-agent", payload["exampleOwner"])

    def test_wrong_claim_id_cannot_update_task(self) -> None:
        claim = issue_queue.claimTask(self.workbook_path, owner="controller/subagent-1")
        with self.assertRaises(issue_queue.QueueError):
            issue_queue.heartbeatTask(
                self.workbook_path,
                issueName=claim["Issue Name"],
                claimId="wrong",
                owner="controller/subagent-1",
                progress=20,
                note="should fail",
            )

    def test_complete_satisfies_dependency(self) -> None:
        claim = issue_queue.claimTask(self.workbook_path, owner="controller/subagent-1")
        issue_queue.finishTask(
            self.workbook_path,
            issueName=claim["Issue Name"],
            claimId=claim["claimId"],
            owner="controller/subagent-1",
            status=issue_queue.STATUS_DONE,
            summary="Implemented and reviewed.",
            validation="python3 -m unittest tests.test_issue_queue: OK",
        )
        next_claim = issue_queue.claimTask(self.workbook_path, owner="controller/subagent-2")
        self.assertEqual(self.issue_c, next_claim["Issue Name"])

        state = issue_queue.loadQueue(self.workbook_path)
        completed = issue_queue.taskByName(state, self.issue_b)
        errors, _ = issue_queue.validateQueueState(state)
        self.assertEqual(issue_queue.STATUS_DONE, completed.status)
        self.assertEqual(100, completed.values["Progress %"])
        self.assertEqual([], errors)

    def test_two_processes_cannot_claim_same_row(self) -> None:
        self.create_workbook(
            [
                self.task_row(self.issue_a, "P0", None, "src/a.cpp"),
                self.task_row(self.issue_b, "P0", None, "src/b.cpp"),
            ]
        )
        context = multiprocessing.get_context("spawn")
        output = context.Queue()
        processes = [
            context.Process(target=claim_worker, args=(str(self.workbook_path), f"worker-{index}", output))
            for index in range(2)
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(20)
            self.assertEqual(0, process.exitcode)
        results = [output.get(timeout=5) for _ in processes]
        self.assertTrue(all(result[0] == "ok" for result in results), results)
        self.assertEqual({self.issue_a, self.issue_b}, {result[1] for result in results})

    def test_reclaim_stale_claim(self) -> None:
        claim = issue_queue.claimTask(self.workbook_path, owner="controller/subagent-1", leaseMinutes=1)
        self.set_claim_times(claim["Issue Name"], lease_minutes_from_now=-10, updated_minutes_ago=10)

        reclaimed = issue_queue.reclaimStaleTasks(self.workbook_path, olderThanMinutes=5)
        self.assertEqual([claim["Issue Name"]], [item["issueName"] for item in reclaimed])
        state = issue_queue.loadQueue(self.workbook_path)
        task = issue_queue.taskByName(state, claim["Issue Name"])
        self.assertEqual(issue_queue.STATUS_NOT_STARTED, task.status)
        self.assertFalse(task.values["Owner"])
        self.assertFalse(task.values["Claim ID"])
        self.assertFalse(task.values["Claimed At UTC"])
        self.assertFalse(task.values["Lease Until UTC"])
        self.assertFalse(task.values["Completed At UTC"])
        self.assertEqual(0, task.values["Progress %"])
        self.assertEqual(1, task.values["Attempt"])
        self.assertIn("controller/subagent-1", task.values["Last Note"])
        self.assertIn(claim["claimId"], task.values["Last Note"])
        self.assertFalse(task.values["Result Summary"])
        self.assertFalse(task.values["Validation Results"])
        errors, warnings = issue_queue.validateQueueState(state)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_stale_claims_detect_expired_in_progress_without_mutating(self) -> None:
        claim = issue_queue.claimTask(self.workbook_path, owner="controller/subagent-1", leaseMinutes=1)
        self.set_claim_times(claim["Issue Name"], lease_minutes_from_now=-10, updated_minutes_ago=10)

        state = issue_queue.loadQueue(self.workbook_path)
        stale = issue_queue.staleClaims(state, olderThanMinutes=5)

        self.assertEqual([claim["Issue Name"]], [item["issueName"] for item in stale])
        self.assertEqual("controller/subagent-1", stale[0]["owner"])
        self.assertEqual(claim["claimId"], stale[0]["claimId"])
        self.assertEqual("lease expired", stale[0]["staleReason"])
        self.assertTrue(stale[0]["leaseExpired"])
        state = issue_queue.loadQueue(self.workbook_path)
        task = issue_queue.taskByName(state, claim["Issue Name"])
        payload = issue_queue.taskPayload(task)
        self.assertTrue(payload["leaseExpired"])
        self.assertEqual("lease expired", payload["staleReason"])
        self.assertEqual(issue_queue.STATUS_IN_PROGRESS, task.status)
        self.assertEqual(claim["claimId"], task.values["Claim ID"])

    def test_validate_warns_about_expired_in_progress_lease(self) -> None:
        claim = issue_queue.claimTask(self.workbook_path, owner="controller/subagent-1", leaseMinutes=1)
        self.set_claim_times(claim["Issue Name"], lease_minutes_from_now=-10)

        state = issue_queue.loadQueue(self.workbook_path)
        errors, warnings = issue_queue.validateQueueState(state)

        self.assertEqual([], errors)
        self.assertTrue(any("IN_PROGRESS lease expired" in warning for warning in warnings), warnings)

    def test_reclaim_stale_claim_ignores_unexpired_lease(self) -> None:
        claim = issue_queue.claimTask(self.workbook_path, owner="controller/subagent-1", leaseMinutes=1)
        self.set_claim_times(claim["Issue Name"], lease_minutes_from_now=10, updated_minutes_ago=30)

        reclaimed = issue_queue.reclaimStaleTasks(self.workbook_path, olderThanMinutes=5)

        self.assertEqual([], reclaimed)
        state = issue_queue.loadQueue(self.workbook_path)
        task = issue_queue.taskByName(state, claim["Issue Name"])
        self.assertEqual(issue_queue.STATUS_IN_PROGRESS, task.status)
        self.assertEqual(claim["claimId"], task.values["Claim ID"])
        self.assertFalse(issue_queue.taskPayload(task)["leaseExpired"])

    def test_reclaim_stale_claim_respects_older_than_grace_period(self) -> None:
        claim = issue_queue.claimTask(self.workbook_path, owner="controller/subagent-1", leaseMinutes=1)
        self.set_claim_times(claim["Issue Name"], lease_minutes_from_now=-10, updated_minutes_ago=1)

        reclaimed = issue_queue.reclaimStaleTasks(self.workbook_path, olderThanMinutes=5)

        self.assertEqual([], reclaimed)
        state = issue_queue.loadQueue(self.workbook_path)
        task = issue_queue.taskByName(state, claim["Issue Name"])
        self.assertEqual(issue_queue.STATUS_IN_PROGRESS, task.status)
        self.assertEqual(claim["claimId"], task.values["Claim ID"])

    def test_reclaimed_claim_rejects_prior_credentials_and_can_be_reclaimed(self) -> None:
        claim = issue_queue.claimTask(self.workbook_path, owner="controller/subagent-1", leaseMinutes=1)
        self.set_claim_times(claim["Issue Name"], lease_minutes_from_now=-10, updated_minutes_ago=10)
        issue_queue.reclaimStaleTasks(self.workbook_path, olderThanMinutes=5)

        with self.assertRaises(issue_queue.QueueError):
            issue_queue.heartbeatTask(
                self.workbook_path,
                issueName=claim["Issue Name"],
                claimId=claim["claimId"],
                owner="controller/subagent-1",
                progress=20,
                note="old claim should fail",
            )
        next_claim = issue_queue.claimTask(
            self.workbook_path,
            owner="controller/subagent-2",
            issueName=claim["Issue Name"],
        )

        self.assertNotEqual(claim["claimId"], next_claim["claimId"])
        self.assertEqual(2, next_claim["Attempt"])

    def test_reclaim_stale_rejects_negative_age_threshold(self) -> None:
        with self.assertRaises(issue_queue.QueueError):
            issue_queue.staleClaims(issue_queue.loadQueue(self.workbook_path), olderThanMinutes=-1)
        with self.assertRaises(issue_queue.QueueError):
            issue_queue.reclaimStaleTasks(self.workbook_path, olderThanMinutes=-1)

    def test_reclaim_stale_dry_run_reports_without_mutating(self) -> None:
        claim = issue_queue.claimTask(self.workbook_path, owner="controller/subagent-1", leaseMinutes=1)
        self.set_claim_times(claim["Issue Name"], lease_minutes_from_now=-10, updated_minutes_ago=10)
        recent_claim = issue_queue.claimTask(self.workbook_path, owner="controller/subagent-2", leaseMinutes=1)
        self.set_claim_times(recent_claim["Issue Name"], lease_minutes_from_now=-10, updated_minutes_ago=1)

        before = self.workbook_path.read_bytes()
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = issue_queue.main(
                [
                    "reclaim-stale",
                    "--workbook",
                    str(self.workbook_path),
                    "--older-than-minutes",
                    "5",
                    "--dry-run",
                ]
            )
        payload = json.loads(stdout.getvalue())

        self.assertEqual(0, exit_code)
        self.assertEqual(str(self.workbook_path.resolve()), payload["workbook"])
        self.assertEqual(5, payload["olderThanMinutes"])
        self.assertEqual(2, payload["staleCount"])
        self.assertEqual(1, payload["reclaimableStaleCount"])
        self.assertEqual({"total": 2, "unexpired": 0, "stale": 2}, payload["activeClaims"])
        self.assertTrue(payload["reclaimSafety"]["leaseOnly"])
        self.assertTrue(payload["reclaimSafety"]["requiresInspection"])
        self.assertEqual([claim["Issue Name"]], [item["issueName"] for item in payload["stale"]])
        self.assertFalse(payload["stale"][0]["reclaimReady"])
        self.assertIn("worker worktree", payload["stale"][0]["requiredInspection"])
        self.assertEqual(before, self.workbook_path.read_bytes())
        state = issue_queue.loadQueue(self.workbook_path)
        task = issue_queue.taskByName(state, claim["Issue Name"])
        recent_task = issue_queue.taskByName(state, recent_claim["Issue Name"])
        self.assertEqual(issue_queue.STATUS_IN_PROGRESS, task.status)
        self.assertEqual(claim["claimId"], task.values["Claim ID"])
        self.assertEqual(issue_queue.STATUS_IN_PROGRESS, recent_task.status)
        self.assertEqual(recent_claim["claimId"], recent_task.values["Claim ID"])

    def test_list_table_marks_expired_in_progress_lease(self) -> None:
        claim = issue_queue.claimTask(self.workbook_path, owner="controller/subagent-1", leaseMinutes=1)
        self.set_claim_times(claim["Issue Name"], lease_minutes_from_now=-10, updated_minutes_ago=10)
        state = issue_queue.loadQueue(self.workbook_path)
        tasks = issue_queue.listTasks(state, {issue_queue.STATUS_IN_PROGRESS}, None, None)

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            issue_queue.printTable(tasks)

        output = stdout.getvalue()
        self.assertIn("LEASE", output)
        self.assertIn("expired", output)

    def test_stale_claims_treat_missing_lease_as_recoverable_stale_state(self) -> None:
        claim = issue_queue.claimTask(self.workbook_path, owner="controller/subagent-1", leaseMinutes=1)
        self.set_claim_times(claim["Issue Name"], lease_minutes_from_now=None, updated_minutes_ago=10)
        state = issue_queue.loadQueue(self.workbook_path)

        errors, warnings = issue_queue.validateQueueState(state)
        stale = issue_queue.staleClaims(state, olderThanMinutes=5)

        self.assertTrue(any("requires valid Lease Until UTC" in error for error in errors), errors)
        self.assertEqual([], warnings)
        self.assertEqual([claim["Issue Name"]], [item["issueName"] for item in stale])
        self.assertEqual("missing lease", stale[0]["staleReason"])

    def test_validate_detects_dependency_cycle(self) -> None:
        self.create_workbook(
            [
                self.task_row(self.issue_a, "P0", self.issue_b, "src/a.cpp"),
                self.task_row(self.issue_b, "P0", self.issue_a, "src/b.cpp"),
            ]
        )
        state = issue_queue.loadQueue(self.workbook_path)
        errors, _ = issue_queue.validateQueueState(state)
        self.assertTrue(any(error.startswith("Dependency cycle:") for error in errors), errors)

    def test_prompt_contains_claim_and_repository_rules(self) -> None:
        claim = issue_queue.claimTask(self.workbook_path, owner="controller/subagent-1")
        state = issue_queue.loadQueue(self.workbook_path)
        prompt = issue_queue.renderWorkerPrompt(issue_queue.taskByName(state, claim["Issue Name"]))
        self.assertIn(claim["claimId"], prompt)
        self.assertIn("Inspect the relevant project files first.", prompt)
        self.assertIn("Do not commit, push, merge, or open a PR", prompt)
        self.assertIn("Report queue milestones to the controller", prompt)
        self.assertIn("The controller owns workbook updates", prompt)
        self.assertIn("Do not run issue_queue.py heartbeat, complete, block, fail, cancel, or release", prompt)
        self.assertNotIn("run a heartbeat", prompt)
        self.assertNotIn("call complete", prompt)
        self.assertNotIn("call block", prompt)

    def test_unrelated_xlsx_parts_are_preserved_byte_for_byte(self) -> None:
        marker_name = "custom/marker.bin"
        marker_value = b"preserve-me"
        with zipfile.ZipFile(self.workbook_path, "a", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(marker_name, marker_value)
        issue_queue.claimTask(self.workbook_path, owner="controller/subagent-1")
        with zipfile.ZipFile(self.workbook_path, "r") as archive:
            self.assertEqual(marker_value, archive.read(marker_name))


if __name__ == "__main__":
    unittest.main()
