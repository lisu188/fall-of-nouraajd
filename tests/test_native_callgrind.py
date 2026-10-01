# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

from contextlib import redirect_stderr
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts import profile_native_tests as profile

ROOT = Path(__file__).resolve().parents[1]


class NativeCallgrindToolTest(unittest.TestCase):
    def setUp(self):
        scratch_root = ROOT / "build"
        scratch_root.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="native-callgrind-check-", dir=scratch_root)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.build_dir = self.root / "cmake-build-relwithdebinfo"
        self.build_dir.mkdir()
        self.binary = self.build_dir / "handler_unit_tests"
        self.binary.write_text("fixture", encoding="utf-8")
        self.tools = {name: "/tools/" + name for name in ("valgrind", "callgrind_annotate", "xvfb-run", "xauth")}

    def fakeProcess(self, return_code=0, readable=True):
        process = Mock(pid=8123)
        process.wait.return_value = return_code

        def start(command, **kwargs):
            self.command = command
            self.environment = kwargs["env"]
            self.assertEqual(self.build_dir, kwargs["cwd"])
            self.assertTrue(kwargs["start_new_session"])
            kwargs["stdout"].write("native output retained\n")
            kwargs["stderr"].write("native diagnostic retained\n")
            path = next(
                argument.split("=", 1)[1] for argument in command if argument.startswith("--callgrind-out-file=")
            )
            if readable:
                Path(path).write_text("events: Ir\nsummary: 1234\n", encoding="utf-8")
            return process

        return process, start

    def testWholeBinaryRunsOnXvfbWithSoftwareRenderingAndNoFilters(self):
        command = profile.profileCommand(
            self.binary, self.root / "callgrind.out", self.root / "valgrind.log", self.tools
        )
        self.assertEqual(self.tools["xvfb-run"], command[0])
        self.assertIn("--server-args=-screen 0 1920x1080x24", command)
        self.assertIn("--tool=callgrind", command)
        self.assertEqual(str(self.binary), command[-1])
        self.assertFalse(any("filter" in argument or "test-case" in argument for argument in command))
        process, start = self.fakeProcess()
        with (
            patch.object(profile.subprocess, "Popen", side_effect=start),
            patch.object(profile, "annotateProfile", return_value=[{"returnCode": 0}]),
        ):
            record = profile.runProfile("handler", self.binary, self.build_dir, self.root / "result", self.tools, 1800)
        self.assertTrue(record["complete"])
        self.assertEqual("completed", record["status"])
        self.assertEqual(
            profile.DISPLAY_ENVIRONMENT, {key: self.environment[key] for key in profile.DISPLAY_ENVIRONMENT}
        )
        process.wait.assert_called_once_with(timeout=1800)

    def testNativeFailureKeepsRawAndAnnotatedPartialEvidence(self):
        _process, start = self.fakeProcess(return_code=7)
        output = self.root / "failed"
        with (
            patch.object(profile.subprocess, "Popen", side_effect=start),
            patch.object(
                profile.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0, "Ir function\n1234 stats\n", ""),
            ),
        ):
            record = profile.runProfile("handler", self.binary, self.build_dir, output, self.tools, 1800)
        self.assertEqual(
            ("native-failure", 7, False), (record["status"], record["nativeReturnCode"], record["complete"])
        )
        self.assertTrue(record["profileReadable"])
        self.assertEqual("native output retained\n", (output / "native.stdout.log").read_text())
        self.assertEqual("native diagnostic retained\n", (output / "native.stderr.log").read_text())
        self.assertTrue((output / "inclusive.txt").is_file())
        self.assertTrue((output / "exclusive.txt").is_file())
        self.assertEqual(record, json.loads((output / "result.json").read_text()))

    def testDiagnosticTimeoutNeverBecomesCompleteEvidence(self):
        process, start = self.fakeProcess()
        process.wait.side_effect = [subprocess.TimeoutExpired("fixture", 1800), 130]
        with (
            patch.object(profile.subprocess, "Popen", side_effect=start),
            patch.object(profile.os, "killpg", create=True) as kill_group,
            patch.object(profile, "annotateProfile", return_value=[{"returnCode": 0}]),
        ):
            record = profile.runProfile("handler", self.binary, self.build_dir, self.root / "timeout", self.tools, 1800)
        kill_group.assert_called_once_with(process.pid, signal.SIGINT)
        self.assertEqual("timeout", record["status"])
        self.assertTrue(record["timedOut"])
        self.assertTrue(record["profileReadable"])
        self.assertFalse(record["complete"])

    @unittest.skipIf(os.name == "nt", "Linux diagnostic process-group termination fixture")
    def testUnresponsiveProfileProcessIsTerminatedAsAPartialRun(self):
        process, start = self.fakeProcess()
        process.wait.side_effect = [
            subprocess.TimeoutExpired("fixture", 1800),
            subprocess.TimeoutExpired("fixture", 10),
            -9,
        ]
        with (
            patch.object(profile.subprocess, "Popen", side_effect=start),
            patch.object(profile.os, "killpg", create=True) as kill_group,
            patch.object(profile, "annotateProfile", return_value=[{"returnCode": 0}]),
        ):
            record = profile.runProfile("handler", self.binary, self.build_dir, self.root / "killed", self.tools, 1800)
        self.assertEqual([signal.SIGINT, signal.SIGKILL], [call.args[1] for call in kill_group.call_args_list])
        self.assertEqual(-9, record["nativeReturnCode"])
        self.assertFalse(record["complete"])

    def testMissingProfileCannotPassEvenWhenTheNativeProcessReturnsZero(self):
        _process, start = self.fakeProcess(readable=False)
        with (
            patch.object(profile.subprocess, "Popen", side_effect=start),
            patch.object(profile, "annotateProfile") as annotate,
        ):
            record = profile.runProfile("handler", self.binary, self.build_dir, self.root / "missing", self.tools, 1800)
        self.assertEqual("missing-profile", record["status"])
        self.assertFalse(record["complete"])
        annotate.assert_not_called()

    def testAnnotationFailuresAreReportedWithoutClaimingCompleteEvidence(self):
        for result in (
            subprocess.CompletedProcess([], 3, "partial annotation\n", "parse failed\n"),
            subprocess.TimeoutExpired("fixture", 60),
        ):
            with self.subTest(result=result):
                _process, start = self.fakeProcess()
                output = self.root / ("annotation-timeout" if isinstance(result, Exception) else "annotation-failed")
                run_kwargs = {"side_effect": result} if isinstance(result, Exception) else {"return_value": result}
                with (
                    patch.object(profile.subprocess, "Popen", side_effect=start),
                    patch.object(profile.subprocess, "run", **run_kwargs),
                ):
                    record = profile.runProfile("handler", self.binary, self.build_dir, output, self.tools, 1800)
                self.assertEqual("annotation-failure", record["status"])
                self.assertFalse(record["complete"])
                self.assertTrue((output / "callgrind.out").is_file())
                self.assertEqual(record, json.loads((output / "result.json").read_text()))

    def testEmptyOrMalformedInstructionCountsCannotBecomeRoutineEvidence(self):
        target = self.root / "counts.out"
        for contents in (
            "events: Ir\n",
            "events: Ir\nsummary: 0\n",
            "events: Ir\nsummary: broken\n",
            "events: Ir Dr\nsummary: 0 1234\n",
            "events: Ir Dr\nsummary: 1234\n",
        ):
            with self.subTest(contents=contents):
                target.write_text(contents, encoding="utf-8")
                self.assertFalse(profile.validProfile(target))
        target.write_text("events: Ir\nsummary: 1234\n", encoding="utf-8")
        self.assertTrue(profile.validProfile(target))

    def testUnavailableVirtualDisplayToolRejectsBeforeNativeExecution(self):
        with (
            patch.object(profile.sys, "platform", "linux"),
            patch.object(
                profile.shutil, "which", side_effect=lambda name: None if name == "xauth" else "/tools/" + name
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "xauth"):
                profile.selectedTools()

    def testSelectedMetadataNeverDumpsTheEnvironmentOrUnrelatedCacheValues(self):
        cache = self.build_dir / "CMakeCache.txt"
        cache.write_text(
            "CMAKE_BUILD_TYPE:STRING=RelWithDebInfo\nCMAKE_CXX_COMPILER:FILEPATH=/tools/c++\n"
            "CMAKE_CXX_FLAGS_RELWITHDEBINFO:STRING=-O2 -g -DNDEBUG\nPRIVATE_TOKEN:STRING=private-value\n",
            encoding="utf-8",
        )
        with (
            patch.dict(os.environ, {"PRIVATE_TOKEN": "environment-secret"}),
            patch.object(
                profile.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "selected metadata\n", "")
            ),
        ):
            metadata = profile.buildMetadata(self.root, self.build_dir, self.tools)
        encoded = json.dumps(metadata)
        self.assertNotIn("PRIVATE_TOKEN", encoded)
        self.assertNotIn("environment-secret", encoded)
        self.assertNotIn("private-value", encoded)
        self.assertEqual("RelWithDebInfo", metadata["cmake"]["CMAKE_BUILD_TYPE"])
        self.assertEqual(set(profile.DISPLAY_ENVIRONMENT), set(metadata["display"]))

    def testPathsCannotEscapeTheRepositoryAndExistingEvidenceIsPreserved(self):
        with self.assertRaises(ValueError):
            profile.projectPath(self.root, "../outside")
        output = self.root / "test/native-callgrind/existing"
        output.mkdir(parents=True)
        retained = output / "failure.log"
        retained.write_text("keep this evidence", encoding="utf-8")
        with patch.object(profile, "selectedTools", return_value=self.tools), redirect_stderr(io.StringIO()):
            status = profile.main(["--repo-root", str(self.root), "--output-dir", str(output), "--suite", "handler"])
        self.assertEqual(2, status)
        self.assertEqual("keep this evidence", retained.read_text())

    def testSetupMetadataIsRetainedWithoutClaimingOrRunningTheNativeWorkload(self):
        output = self.root / "test/native-callgrind/setup"
        with (
            patch.object(profile, "selectedTools", return_value=self.tools),
            patch.object(profile, "buildMetadata", return_value={"checkout": {"firstLine": "verified-sha"}}),
            patch.object(profile, "runProfile") as run_profile,
        ):
            status = profile.main(["--repo-root", str(self.root), "--output-dir", str(output), "--metadata-only"])
        self.assertEqual(0, status)
        run_profile.assert_not_called()
        manifest = json.loads((output / "manifest.json").read_text())
        self.assertEqual("diagnostic-callgrind-setup", manifest["kind"])
        self.assertEqual([], manifest["results"])

    def testEarlierNativeTimingEvidenceCannotBeOverwrittenByAFreshOutputDirectory(self):
        for suite in ("handler", "map"):
            with self.subTest(suite=suite):
                (self.build_dir / profile.SUITE_BINARIES[suite]).write_text("fixture", encoding="utf-8")
                timing_dir = self.root / "coverage/native-test-profiles"
                timing_dir.mkdir(parents=True, exist_ok=True)
                timing_file = timing_dir / (suite + ".tsv")
                timing_file.write_text("partial failed native timing evidence\n", encoding="utf-8")
                output = self.root / ("test/native-callgrind/fresh-" + suite)
                with (
                    patch.object(profile, "selectedTools", return_value=self.tools),
                    patch.object(profile, "buildMetadata", return_value={}),
                    patch.object(
                        profile, "runProfile", return_value={"complete": True, "status": "completed"}
                    ) as run_profile,
                    redirect_stderr(io.StringIO()),
                ):
                    status = profile.main(
                        ["--repo-root", str(self.root), "--output-dir", str(output), "--suite", suite]
                    )
                self.assertEqual(2, status)
                run_profile.assert_not_called()
                self.assertFalse(output.exists())
                self.assertEqual("partial failed native timing evidence\n", timing_file.read_text())

    @unittest.skipIf(os.name == "nt", "Linux diagnostic symlink fixture")
    def testSymlinkEscapeIsRejectedBeforeWriting(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.root / "escape").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                profile.projectPath(self.root, "escape/profile")

    def testWorkflowIsNarrowDiagnosticAndRetainsFailuresWithoutChangingNormalGates(self):
        workflow = (ROOT / ".github/workflows/profile-native.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("pull_request:", workflow)
        self.assertNotIn("pull_request_target", workflow)
        self.assertIn("paths:\n      - .github/workflows/profile-native.yml", workflow)
        self.assertIn("timeout-minutes: 90", workflow)
        self.assertIn("--timeout-seconds 1800", workflow)
        self.assertIn("if: always()", workflow)
        self.assertIn("handler_unit_tests map_unit_tests", workflow)
        self.assertNotIn("ctest ", workflow)
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertRegex(cmake, r'LABELS "for_unit_tests;unit;\$\{target_name\}"\s+TIMEOUT 60')


if __name__ == "__main__":
    unittest.main()
