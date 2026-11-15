"""Regression checks for exhaustive recovery sharding and locked toolchains."""

import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("recovery_shards", ROOT / "recovery/toolchains/plan_shards.py")
SHARDS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SHARDS)


class RecoveryWorkflowTest(unittest.TestCase):
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
