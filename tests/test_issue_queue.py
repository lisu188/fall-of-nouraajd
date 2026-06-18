from __future__ import annotations

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
        document = issue_queue.XlsxDocument.load(self.workbook_path)
        state = issue_queue.loadQueue(self.workbook_path)
        task = issue_queue.taskByName(state, claim["Issue Name"])
        past = issue_queue.formatUtc(issue_queue.utcNow() - timedelta(minutes=10))
        document.setCell(task.row, state.headers["Lease Until UTC"], past)
        document.setCell(task.row, state.headers["Updated At UTC"], past)
        document.save(self.workbook_path)

        reclaimed = issue_queue.reclaimStaleTasks(self.workbook_path, olderThanMinutes=5)
        self.assertEqual([claim["Issue Name"]], [item["issueName"] for item in reclaimed])
        state = issue_queue.loadQueue(self.workbook_path)
        task = issue_queue.taskByName(state, claim["Issue Name"])
        self.assertEqual(issue_queue.STATUS_NOT_STARTED, task.status)
        self.assertFalse(task.values["Claim ID"])

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
