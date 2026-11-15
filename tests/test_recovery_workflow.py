"""Regression checks for exhaustive recovery sharding and locked toolchains."""

import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("recovery_shards", ROOT / "recovery/toolchains/plan_shards.py")
SHARDS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SHARDS)


class RecoveryWorkflowTest(unittest.TestCase):
    def testStackedRecoveryPullRequestsRunTheExhaustiveWorkflow(self):
        workflow = (ROOT / ".github/workflows/recover-history.yml").read_text()
        trigger = workflow.split("  pull_request:\n", 1)[1].split("\npermissions:", 1)[0]
        self.assertNotRegex(trigger, r"(?m)^    branches(?:-ignore)?:")
        self.assertIn("      - recovery/**", trigger)
        self.assertIn("scripts/verify_history.py --all", workflow)
        self.assertIn("--trees-per-shard 16", workflow)
        self.assertIn("max-parallel: 4", workflow)

    def testEveryTreeAssignedExactlyOnceWithinBudget(self):
        trees = [{"tree": str(index)} for index in range(365)]
        matrix = SHARDS.planShards({"trees": trees, "summary": {"damagedTreeCount": len(trees)}})
        assigned = []
        self.assertLessEqual(len(matrix["include"]), 256)
        for shard in matrix["include"]:
            subset = trees[shard["index"] :: shard["count"]]
            self.assertLessEqual(len(subset), 16)
            assigned.extend(tree["tree"] for tree in subset)
        self.assertEqual(sorted(assigned), sorted(tree["tree"] for tree in trees))

    def testInvalidCatalogCannotProducePassingEmptyMatrix(self):
        for trees, expected in (([], 0), ([{"tree": "same"}] * 2, 2), ([{"tree": "a"}], 2)):
            with self.subTest(trees=trees, expected=expected), self.assertRaises(ValueError):
                SHARDS.planShards({"trees": trees, "summary": {"damagedTreeCount": expected}})

    def testOversizedMatrixFailsExplicitly(self):
        trees = [{"tree": str(index)} for index in range(257)]
        with self.assertRaisesRegex(ValueError, "256-job"):
            SHARDS.planShards({"trees": trees, "summary": {"damagedTreeCount": len(trees)}}, 1)

    def testPythonAbisHaveSeparateHeadersLibrariesAndHomes(self):
        catalog = json.loads((ROOT / "recovery/toolchains/qt5.json").read_text())
        recipes = catalog["recipes"]
        self.assertEqual({recipe["pythonAbi"] for recipe in recipes}, {"none", "2.7", "3.3", "3.4"})
        homes = set()
        for recipe in recipes:
            environment = recipe["environment"]
            if recipe["pythonAbi"] == "none":
                self.assertNotIn("PYTHONHOME", environment)
                continue
            home = environment["PYTHONHOME"]
            self.assertNotIn(home, homes)
            homes.add(home)
            self.assertIn(home + "/lib", environment["LD_LIBRARY_PATH"].split(":"))
            self.assertIn(home + "/lib", environment["LIBRARY_PATH"].split(":"))
            self.assertTrue(any(path.startswith(home + "/include/python") for path in environment["CPATH"].split(":")))

    def testGitSourceLockPinsReleaseCommitsAndTheIdenticalBoostArchive(self):
        official = json.loads((ROOT / "recovery/toolchains/sources.json").read_text())["sources"]
        alternative = json.loads((ROOT / "recovery/toolchains/sources-git.json").read_text())["sources"]
        self.assertEqual([source["name"] for source in official], [source["name"] for source in alternative])
        for source, original in zip(alternative, official, strict=True):
            self.assertRegex(source["sha256"], r"^[0-9a-f]{64}$")
            if "git" in source:
                version = source["name"].split("-")[1]
                self.assertEqual("v" + version, source["git"]["tag"])
                self.assertRegex(source["git"]["commit"], r"^[0-9a-f]{40}$")
                self.assertEqual(f"Python-{version}.git.tar", source["archive"])
            else:
                self.assertEqual(original["sha256"], source["sha256"])
                self.assertTrue(all(url.startswith("https://") for url in source.get("mirrors", [])))

    def testToolchainBuildPatchesBoostPythonForPython33AndLogsVerboseSteps(self):
        script = (ROOT / "recovery/toolchains/build.sh").read_text()
        self.assertIn("PY_VERSION_HEX >= 0x03040000", script)
        self.assertIn("runLogged", script)
        self.assertIn("/usr/lib/x86_64-linux-gnu/qt5/bin/qmake -query QT_VERSION", script)

    def testWorkflowRunsOnlyExistingRecoveryTestModules(self):
        workflow = (ROOT / ".github/workflows/recover-history.yml").read_text()
        modules = set(re.findall(r"\btests\.(test_\w+)", workflow))
        triggers = set(re.findall(r"^\s*- tests/(test_\w+)\.py$", workflow, re.MULTILINE))
        self.assertTrue(modules)
        self.assertEqual(
            set(), {name for name in modules | triggers if not (ROOT / "tests" / (name + ".py")).is_file()}
        )
        self.assertEqual(modules, triggers)

    def testAllDownloadedSourcesHaveUniquePinnedIdentities(self):
        lock = json.loads((ROOT / "recovery/toolchains/sources.json").read_text())
        names = set()
        for source in lock["sources"]:
            self.assertNotIn(source["name"], names)
            names.add(source["name"])
            self.assertTrue(source["url"].startswith("https://"))
            self.assertRegex(source["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(len(names), 5)


if __name__ == "__main__":
    unittest.main()
