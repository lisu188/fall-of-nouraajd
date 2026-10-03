# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import pathlib
import io
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from scripts import run_monster_balance as runner

ROOT = pathlib.Path(__file__).resolve().parents[1]


class MonsterBalanceRunnerTest(unittest.TestCase):
    def runFixture(self, mode, timeout=10, diagnostic_output_dir=None):
        lines = []
        with tempfile.TemporaryDirectory(prefix="nouraajd-role-runner-") as directory:
            fixture = pathlib.Path(directory) / "native_fixture.py"
            fixture.write_text(
                "import sys,time\n"
                "mode=sys.argv[1]\n"
                "args=sys.argv[2:]\n"
                "if args==['--contracts-only']:\n"
                " print('contracts started',flush=True)\n"
                " if mode!='contracts-fail': print('role contracts complete',flush=True)\n"
                " raise SystemExit(1 if mode=='contracts-fail' else 0)\n"
                "name=args[1]\n"
                "print('partition started '+name,flush=True)\n"
                "if mode=='timeout': time.sleep(30)\n"
                "if mode=='stderr-flood': print('x'*200000,file=sys.stderr,flush=True)\n"
                "if mode=='stderr-success': print('retained native diagnostic '+name,file=sys.stderr,flush=True)\n"
                f"monsters={runner.MONSTER_IDS!r}\n"
                "for monster in monsters:\n"
                " if mode=='missing-row' and name=='Warrior' and monster=='Pritz': continue\n"
                " print('role balance '+name+'/'+monster+' hp 1 -> 1',flush=True)\n"
                "if mode=='duplicate-row' and name=='Warrior': print('role balance Warrior/Gooby hp 1 -> 1')\n"
                "counts='rows=7 pairedSeeds=77 fights=154'\n"
                "if mode=='wrong-count' and name=='Warrior': counts='rows=7 pairedSeeds=76 fights=152'\n"
                "print('role class complete '+name+' '+counts,flush=True)\n"
                "if mode=='assertion-fail' and name=='Warrior':\n"
                " print('FAIL: strict seeded victory regression',file=sys.stderr,flush=True)\n"
                " raise SystemExit(1)\n",
                encoding="utf-8",
            )
            result = runner.runMatrix(
                [sys.executable, str(fixture), mode],
                timeout=timeout,
                emit=lines.append,
                diagnostic_output_dir=diagnostic_output_dir,
            )
        return result, lines

    def testEveryClassAndAll770FightsCompleteWithCommonContractsOnce(self):
        result, lines = self.runFixture("success")
        self.assertEqual(0, result)
        self.assertEqual(1, sum("contracts started" in line for line in lines))
        self.assertEqual(5, sum("partition started" in line for line in lines))
        self.assertEqual(35, sum("role balance " in line for line in lines))
        self.assertIn("role matrix complete classes=5 rows=35 pairedSeeds=385 fights=770 commonContracts=1", lines)

    def testMissingDuplicateOrWrongCountCannotSatisfyCompletion(self):
        for mode in ("missing-row", "duplicate-row", "wrong-count"):
            with self.subTest(mode=mode):
                self.assertEqual(1, self.runFixture(mode)[0])

    def testNativeAssertionFailureStillFailsAndPreservesDiagnostic(self):
        result, lines = self.runFixture("assertion-fail")
        self.assertEqual(1, result)
        self.assertTrue(any("strict seeded victory regression" in line for line in lines))

    def testCommonFailureNeverStartsPartitions(self):
        result, lines = self.runFixture("contracts-fail")
        self.assertEqual(1, result)
        self.assertFalse(any("partition started" in line for line in lines))

    def testStderrIsDrainedConcurrentlyWithoutDeadlock(self):
        result, lines = self.runFixture("stderr-flood")
        self.assertEqual(0, result)
        self.assertEqual(5, sum(len(line) > 200000 for line in lines))

    def testSuccessfulWorkersRetainSeparateStdoutAndStderrWithoutReplacingFiles(self):
        with tempfile.TemporaryDirectory(prefix="nouraajd-role-diagnostics-") as directory:
            output = pathlib.Path(directory) / "nested" / "native-role-diagnostics"
            for attempt in range(2):
                result, lines = self.runFixture("stderr-success", diagnostic_output_dir=output)
                self.assertEqual(0, result)
                self.assertIn(
                    "role matrix complete classes=5 rows=35 pairedSeeds=385 fights=770 commonContracts=1", lines
                )
                self.assertEqual(12 * (attempt + 1), len(list(output.glob("*.log"))))
                for class_id in runner.CLASS_IDS:
                    stdout = list(output.glob(f"{class_id}-*.stdout.log"))
                    stderr = list(output.glob(f"{class_id}-*.stderr.log"))
                    self.assertEqual(attempt + 1, len(stdout))
                    self.assertEqual(attempt + 1, len(stderr))
                    for path in stdout:
                        content = path.read_text(encoding="utf-8")
                        self.assertIn(f"role class complete {class_id} rows=7 pairedSeeds=77 fights=154", content)
                        self.assertEqual(7, content.count("role balance "))
                    for path in stderr:
                        self.assertEqual(f"retained native diagnostic {class_id}\n", path.read_text(encoding="utf-8"))

    def testRetainedDiagnosticsPreserveNativeAssertionFailureAndConcurrentFloodDrain(self):
        with tempfile.TemporaryDirectory(prefix="nouraajd-role-diagnostics-") as directory:
            output = pathlib.Path(directory)
            self.assertEqual(1, self.runFixture("assertion-fail", diagnostic_output_dir=output)[0])
            stderr = list(output.glob("Warrior-*.stderr.log"))
            self.assertEqual(1, len(stderr))
            self.assertIn("strict seeded victory regression", stderr[0].read_text(encoding="utf-8"))
            self.assertEqual(0, self.runFixture("stderr-flood", diagnostic_output_dir=output)[0])
            floods = [path for path in output.glob("*.stderr.log") if path.stat().st_size > 200000]
            self.assertEqual(5, len(floods))

    def testDefaultRunnerDoesNotOpenDiagnosticFiles(self):
        with patch.object(runner, "openDiagnosticStreams", side_effect=AssertionError("unexpected file logging")):
            self.assertEqual(0, self.runFixture("success")[0])

    def testDiagnosticWriteFailureStillDrainsPipesAndCannotPassTheGate(self):
        writer = Mock()
        writer.write.side_effect = OSError("diagnostic disk unavailable")
        process = Mock()
        process.stdout = io.StringIO("first\nsecond\n")
        process.stderr = io.StringIO("native error\n")
        process.wait.return_value = 0
        process.poll.return_value = 0
        lines = []
        with (
            patch.object(runner, "openDiagnosticStreams", return_value=[writer, None]),
            patch.object(runner.subprocess, "Popen", return_value=process),
        ):
            result = runner.runWorker(
                ["fixture"],
                "Warrior",
                time.monotonic() + 10,
                lines.append,
                threading.Lock(),
                threading.Event(),
                "diagnostic-output",
            )
        self.assertEqual(["first", "second"], result.stdout)
        self.assertEqual(0, result.return_code)
        self.assertFalse(result.complete_streams)
        self.assertFalse(runner.validateWorker(result))
        self.assertTrue(any("native error" in line for line in lines))
        writer.write.assert_called_once()
        writer.close.assert_called_once()

    def testReaderFailureCannotMasqueradeAsSuccessfulEndOfStream(self):
        class BrokenStream:
            def __iter__(self):
                raise OSError("native pipe read failed")

            def close(self):
                pass

        complete_stdout = "\n".join(
            [f"role balance Warrior/{monster_id} hp 1 -> 1" for monster_id in runner.MONSTER_IDS]
            + ["role class complete Warrior rows=7 pairedSeeds=77 fights=154"]
        )
        for broken_stdout in (False, True):
            with self.subTest(broken_stdout=broken_stdout):
                process = Mock()
                process.stdout = BrokenStream() if broken_stdout else io.StringIO(complete_stdout)
                process.stderr = io.StringIO("") if broken_stdout else BrokenStream()
                process.wait.return_value = 0
                process.poll.return_value = 0
                lines = []
                with patch.object(runner.subprocess, "Popen", return_value=process):
                    result = runner.runWorker(
                        ["fixture"], "Warrior", time.monotonic() + 10, lines.append, threading.Lock(), threading.Event()
                    )
                self.assertEqual(0, result.return_code)
                self.assertFalse(result.complete_streams)
                self.assertFalse(runner.validateWorker(result))
                self.assertTrue(any("OSError: native pipe read failed" in line for line in lines))

    def testAggregateDeadlineKillsAndReapsRunningWorkers(self):
        processes = []
        original_popen = runner.subprocess.Popen

        def recordProcess(*args, **kwargs):
            process = original_popen(*args, **kwargs)
            processes.append(process)
            return process

        started = time.monotonic()
        with patch.object(runner.subprocess, "Popen", side_effect=recordProcess):
            result, lines = self.runFixture("timeout", timeout=1)
        self.assertEqual(1, result)
        self.assertTrue(any("partition started" in line for line in lines))
        self.assertGreater(len(processes), 1)
        self.assertTrue(all(process.returncode is not None for process in processes))
        self.assertLess(time.monotonic() - started, 6)

    def testOuterGateAndNativeClosedWhitelistPreserveOriginalWorkload(self):
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        helper = cmake.split("function(add_game_unit_test target_name)", 1)[1].split("endfunction()", 1)[0]
        self.assertEqual(1, helper.count("TIMEOUT 60"))
        self.assertIn("scripts/run_monster_balance.py", helper)
        self.assertIn(
            '--diagnostic-output-dir "${CMAKE_CURRENT_SOURCE_DIR}/coverage/test-output/native-role-diagnostics"', helper
        )
        self.assertEqual(4, runner.MAX_WORKERS)
        self.assertEqual(55, runner.TOTAL_SECONDS)
        source = (ROOT / "tests/unit/test_monster_balance.cpp").read_text(encoding="utf-8")
        self.assertIn("seed < 111", source)
        self.assertIn("completedRows == 7 && completedPairedSeeds == 77", source)
        self.assertIn("Unknown role class partition", source)
        self.assertIn("if (selectedClass.empty())", source)
        self.assertIn("if (!contractsOnly)", source)
        self.assertEqual(5, len(runner.CLASS_IDS))
        self.assertEqual(7, len(runner.MONSTER_IDS))
        for class_id in runner.CLASS_IDS:
            self.assertIn(f'"{class_id}"', source)
        with self.assertRaises(ValueError):
            runner.runMatrix([], workers=5)


if __name__ == "__main__":
    unittest.main()
