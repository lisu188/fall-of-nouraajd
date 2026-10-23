# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Execute proposed inline orchestration over tiny synthetic files and fully intercepted subprocesses."""

import ast
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/city-resource-review.yml"
ALLOWED = (
    "res/maps/baldursGate/map.json",
    "res/maps/baldursGate/config.json",
    "res/maps/baldursGate/dialog.json",
    "tests/fixtures/baldurs_gate_city_geometry.json",
)


def allPythonBlocks():
    result, selected = [], None
    for line in WORKFLOW.read_text().splitlines():
        if line in {"          python -B - <<'PY'", "          python3 -B - <<'PY'"}:
            selected = []
        elif selected is not None and line == "          PY":
            source = "\n".join(selected) + "\n"
            ast.parse(source)
            result.append(source)
            selected = None
        elif selected is not None:
            if line and not line.startswith("          "):
                raise ValueError("Malformed proposed inline Python indentation")
            selected.append(line[10:])
    if selected is not None or len(result) != 3:
        raise ValueError("Expected pre-checkout, generation and final stale gate")
    return result


def pythonBlocks():
    return allPythonBlocks()[1:]


@contextmanager
def syntheticRun(mode):
    with tempfile.TemporaryDirectory(prefix="city-resource-review-") as directory:
        root = Path(directory).resolve()
        workspace, runner = root / "workspace", root / "runner"
        workspace.mkdir()
        runner.mkdir()
        for relative in ALLOWED:
            destination = workspace / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text('{"synthetic":0}\n')
        calls = []

        def fakeCheckOutput(command, **kwargs):
            calls.append(command)
            if command == ["git", "rev-parse", "HEAD"]:
                return (("b" if mode == "wrong-head" else "a") * 40 + "\n").encode()
            if command == ["git", "rev-parse", "HEAD^{tree}"]:
                return ("e" * 40 + "\n").encode()
            if command == ["git", "status", "--porcelain=v1", "--untracked-files=all"]:
                return b""
            if command == ["git", "diff", "--no-ext-diff", "--no-textconv", "--cached", "--name-only"]:
                return b""
            if command == ["git", "diff", "--no-ext-diff", "--no-textconv", "HEAD", "--name-only"]:
                return (
                    b"unexpected.py\n"
                    if mode == "unexpected"
                    else (b"res/maps/baldursGate/config.json\n" if mode in {"stale", "failed-post-check"} else b"")
                )
            if command == ["git", "ls-files", "--others", "--exclude-standard"]:
                return b""
            raise AssertionError("Unplanned subprocess: " + repr(command))

        def fakeRun(command, **kwargs):
            calls.append(command)
            if len(command) >= 3 and command[2] == "scripts/build_baldurs_gate_city.py":
                self_check = command[3:] == ["--check"]
                if not self_check and mode != "clean":
                    (workspace / ALLOWED[1]).write_text('{"synthetic":1}\n')
                return subprocess.CompletedProcess(
                    command,
                    1 if self_check and mode == "failed-post-check" else 0,
                    stdout=b"synthetic subprocess; actual generator never executed\n",
                )
            if command[:5] == ["git", "diff", "--no-ext-diff", "--no-textconv", "--binary"]:
                target = Path(next(part.removeprefix("--output=") for part in command if part.startswith("--output=")))
                target.write_text("synthetic patch\n" if mode != "clean" else "")
                return subprocess.CompletedProcess(command, 0)
            raise AssertionError("Unplanned executable: " + repr(command))

        def fakeDiskUsage(location):
            generator_calls = sum(len(call) > 2 and call[2] == "scripts/build_baldurs_gate_city.py" for call in calls)
            is_checkout = Path(location) == workspace
            at_fault = ("checkout" in mode and is_checkout) or ("runner" in mode and not is_checkout)
            if mode.startswith("retention-") and generator_calls < 2:
                at_fault = False
            if at_fault and "threshold" in mode:
                return shutil._ntuple_diskusage(10 * 1024**3, 9 * 1024**3, 1024**3)
            if at_fault and "reserve" in mode:
                return shutil._ntuple_diskusage(512 * 1024**2, 400 * 1024**2, 112 * 1024**2)
            if at_fault and "would-cross" in mode:
                total = 10 * 1024**3
                used = total * 89 // 100
                return shutil._ntuple_diskusage(total, used, total - used)
            if mode == "shared-exact-reserve":
                total = 10 * 1024**3
                free = total // 10 + 128 * 1024**2 + 1
                return shutil._ntuple_diskusage(total, total - free, free)
            return shutil._ntuple_diskusage(10 * 1024**3, 1024**3, 9 * 1024**3)

        original_stat = os.stat

        def fakeStat(path, *args, **kwargs):
            value = original_stat(path, *args, **kwargs)
            if Path(path) in {workspace, runner}:
                fields = list(value)
                fields[2] = 1 if Path(path) == workspace or mode == "shared-exact-reserve" else 2
                return os.stat_result(fields)
            return value

        previous = Path.cwd()
        try:
            os.chdir(workspace)
            with patch.dict(
                os.environ,
                GITHUB_ACTIONS="true",
                RUNNER_TEMP=str(runner),
                EXPECTED_HEAD="a" * 40,
                PR_BASE="c" * 40,
                PR_NUMBER="1",
                WORKFLOW_REF="synthetic",
                WORKFLOW_SHA="d" * 40,
                UPLOAD_OUTCOME="success",
                GITHUB_WORKSPACE=str(workspace),
            ), patch.object(subprocess, "check_output", side_effect=fakeCheckOutput), patch.object(
                subprocess, "run", side_effect=fakeRun
            ):
                with patch.object(shutil, "disk_usage", side_effect=fakeDiskUsage), patch.object(
                    os, "stat", side_effect=fakeStat
                ):
                    yield runner / "city-resource-review", calls
        finally:
            os.chdir(previous)


class CityResourceReviewWorkflowTest(unittest.TestCase):
    def testSourceHasAdditivePullRequestHeadAndReadOnlyTokenContract(self):
        source = WORKFLOW.read_text()
        self.assertIn("  pull_request:", source)
        self.assertNotIn("pull_request_target:", source)
        self.assertNotIn("workflow_dispatch:", source)
        self.assertIn("ref: ${{ github.event.pull_request.head.sha }}", source)
        self.assertIn("  contents: read", source)
        self.assertIn("persist-credentials: false", source)
        self.assertIn("submodules: false", source)
        self.assertNotIn("secrets.", source)
        self.assertNotIn("pip install", source)
        self.assertNotIn("cmake", source)
        self.assertNotIn("ci_change_classifier.py", source)
        pythonBlocks()

    def testCleanSourceRetainsOutputsAndPassesFinalGate(self):
        generate, gate = pythonBlocks()
        with syntheticRun("clean") as (output, calls):
            exec(compile(generate, "proposed_ci_inline", "exec"), {})
            exec(compile(gate, "proposed_ci_gate", "exec"), {})
            self.assertEqual(
                2, sum(len(call) > 2 and call[2] == "scripts/build_baldurs_gate_city.py" for call in calls)
            )
            self.assertEqual(4, len(list((output / "generated").rglob("*.json"))))
            receipt = json.loads((output / "receipt.json").read_text())
            self.assertEqual("e" * 40, receipt["checkedOutTree"])
            self.assertFalse(receipt["selectedInputListExhaustive"])
            self.assertIn("selectedInputs", receipt)
            self.assertNotIn("inputs", receipt)

    def testStaleSourceRetainsPatchAndOutputsButCannotPass(self):
        generate, gate = pythonBlocks()
        with syntheticRun("stale") as (output, _calls):
            exec(compile(generate, "proposed_ci_inline", "exec"), {})
            self.assertTrue((output / "generated.patch").read_text())
            self.assertEqual(4, len(list((output / "generated").rglob("*.json"))))
            with self.assertRaisesRegex(AssertionError, "commit only reviewed resources"):
                exec(compile(gate, "proposed_ci_gate", "exec"), {})

    def testFailedPostCheckStillRetainsSelectedOutputsAndFailure(self):
        generate, gate = pythonBlocks()
        with syntheticRun("failed-post-check") as (output, _calls):
            with self.assertRaisesRegex(AssertionError, "post-check failed"):
                exec(compile(generate, "proposed_ci_inline", "exec"), {})
            self.assertEqual(4, len(list((output / "generated").rglob("*.json"))))
            self.assertTrue((output / "post-check.log").exists())
            receipt = json.loads((output / "receipt.json").read_text())
            self.assertFalse(receipt["postCheckPassed"])
            self.assertIn("error", receipt)
            with self.assertRaises(AssertionError):
                exec(compile(gate, "proposed_ci_gate", "exec"), {})

    def testUnexpectedTrackedChangeFailsWithoutExportingOtherSource(self):
        generate, _gate = pythonBlocks()
        with syntheticRun("unexpected") as (output, _calls):
            with self.assertRaisesRegex(AssertionError, "unexpected tracked path"):
                exec(compile(generate, "proposed_ci_inline", "exec"), {})
            self.assertFalse((output / "generated/unexpected.py").exists())
            self.assertIn("error", json.loads((output / "receipt.json").read_text()))

    def testWrongHeadRejectsBeforeAnyGeneratorCommand(self):
        generate, _gate = pythonBlocks()
        with syntheticRun("wrong-head") as (output, calls):
            with self.assertRaises(AssertionError):
                exec(compile(generate, "proposed_ci_inline", "exec"), {})
            self.assertFalse(any(len(call) > 2 and call[2] == "scripts/build_baldurs_gate_city.py" for call in calls))
            self.assertIn("error", json.loads((output / "receipt.json").read_text()))

    def testNinetyPercentOnEitherVolumeRejectsBeforeGeneration(self):
        generate, _gate = pythonBlocks()
        for volume in ("checkout", "runner"):
            with self.subTest(volume=volume), syntheticRun(volume + "-threshold") as (output, calls):
                with self.assertRaisesRegex(AssertionError, "90% disk guard"):
                    exec(compile(generate, "proposed_ci_inline", "exec"), {})
                self.assertFalse(
                    any(len(call) > 2 and call[2] == "scripts/build_baldurs_gate_city.py" for call in calls)
                )
                self.assertFalse((output / "generated").exists())

    def testMissingReserveOnEitherVolumeRejectsBeforeGeneration(self):
        generate, _gate = pythonBlocks()
        for volume in ("checkout", "runner"):
            with self.subTest(volume=volume), syntheticRun(volume + "-reserve") as (output, calls):
                with self.assertRaisesRegex(AssertionError, "128 MiB bounded write reserve"):
                    exec(compile(generate, "proposed_ci_inline", "exec"), {})
                self.assertFalse(
                    any(len(call) > 2 and call[2] == "scripts/build_baldurs_gate_city.py" for call in calls)
                )
                self.assertFalse((output / "generated").exists())

    def testCapacityRecheckBlocksRetentionAfterGeneration(self):
        generate, gate = pythonBlocks()
        for volume in ("checkout", "runner"):
            with self.subTest(volume=volume), syntheticRun("retention-" + volume + "-reserve") as (output, _calls):
                exec(compile(generate, "proposed_ci_inline", "exec"), {})
                self.assertFalse((output / "generated").exists())
                self.assertFalse((output / "generated.patch").exists())
                receipt = json.loads((output / "receipt.json").read_text())
                self.assertIn("retentionError", receipt)
                self.assertEqual({"checkout", "runnerTemp"}, set(receipt["capacity"]["beforeRetention"]))
                with self.assertRaises(AssertionError):
                    exec(compile(gate, "proposed_ci_gate", "exec"), {})

    def testFailedArtifactUploadCannotPassFinalGate(self):
        generate, gate = pythonBlocks()
        with syntheticRun("clean"):
            exec(compile(generate, "proposed_ci_inline", "exec"), {})
            with patch.dict(os.environ, UPLOAD_OUTCOME="failure"), self.assertRaisesRegex(
                AssertionError, "artifact upload failed"
            ):
                exec(compile(gate, "proposed_ci_gate", "exec"), {})

    def testBelowThresholdButProjectedWritesWouldCrossRejectsBeforeGeneration(self):
        generate, _gate = pythonBlocks()
        for volume in ("checkout", "runner"):
            with self.subTest(volume=volume), syntheticRun(volume + "-would-cross") as (output, calls):
                with self.assertRaisesRegex(AssertionError, "would cross 90% disk guard"):
                    exec(compile(generate, "proposed_ci_inline", "exec"), {})
                self.assertFalse(
                    any(len(call) > 2 and call[2] == "scripts/build_baldurs_gate_city.py" for call in calls)
                )
                self.assertFalse((output / "generated").exists())

    def testSharedBackingVolumeChargesCombinedReserveOnce(self):
        generate, _gate = pythonBlocks()
        with syntheticRun("shared-exact-reserve") as (output, _calls):
            exec(compile(generate, "proposed_ci_inline", "exec"), {})
            receipt = json.loads((output / "receipt.json").read_text())
            self.assertNotIn("error", receipt)
            self.assertNotIn("retentionError", receipt)
            before = receipt["capacity"]["beforeGeneration"]
            self.assertEqual(before["checkout"]["volume"], before["runnerTemp"]["volume"])

    def testPreCheckoutCapacityCheckRunsWithoutAnySubprocess(self):
        precheck = allPythonBlocks()[0]
        for mode in ("clean", "checkout-threshold", "runner-threshold"):
            with self.subTest(mode=mode), syntheticRun(mode) as (_output, calls):
                if mode == "clean":
                    exec(compile(precheck, "proposed_ci_precheckout", "exec"), {})
                else:
                    with self.assertRaisesRegex(AssertionError, "90% disk guard before checkout"):
                        exec(compile(precheck, "proposed_ci_precheckout", "exec"), {})
                self.assertEqual([], calls)


if __name__ == "__main__":
    unittest.main()
