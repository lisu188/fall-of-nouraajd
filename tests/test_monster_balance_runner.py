# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import pathlib
import sys
import tempfile
import time
import unittest

from scripts import run_monster_balance as runner

ROOT = pathlib.Path(__file__).resolve().parents[1]


class MonsterBalanceRunnerTest(unittest.TestCase):
    def runFixture(self, mode, timeout=10):
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
            result = runner.runMatrix([sys.executable, str(fixture), mode], timeout=timeout, emit=lines.append)
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

    def testAggregateDeadlineKillsAndReapsRunningWorkers(self):
        started = time.monotonic()
        result, lines = self.runFixture("timeout", timeout=1)
        self.assertEqual(1, result)
        self.assertTrue(any("partition started" in line for line in lines))
        self.assertLess(time.monotonic() - started, 6)

    def testOuterGateAndNativeClosedWhitelistPreserveOriginalWorkload(self):
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        helper = cmake.split("function(add_game_unit_test target_name)", 1)[1].split("endfunction()", 1)[0]
        self.assertEqual(1, helper.count("TIMEOUT 60"))
        self.assertIn("scripts/run_monster_balance.py", helper)
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
