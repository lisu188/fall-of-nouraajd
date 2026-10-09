# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure scheduling, provenance, and suite routing checks for the exhaustive routes."""

from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from scripts import mcp_branch_shards as shards
from tests.gameplay_branch_types import PLAYER_CLASSES, RouteCase, testName


def route():
    pass


class McpBranchShardsTest(unittest.TestCase):
    def runtimeModules(self, prefix=""):
        sources = {
            "game.py": "res/game.py",
            "ui.py": "res/ui.py",
            "campaign.py": "res/campaign.py",
            "narrative.py": "res/narrative.py",
            "game_diagnostics.py": "game_diagnostics.py",
            "quest_state.py": "quest_state.py",
        }
        return {
            (Path(prefix) / name).as_posix(): (shards.ROOT / source).read_bytes() for name, source in sources.items()
        }

    def cases(self):
        return tuple(
            RouteCase(f"route_{index}", "group", ("test",), (f"branch_{index}",), route, duration_seconds=duration)
            for index, duration in enumerate((1200, 400, 200, 100))
        )

    def testWeightedShardsCoverEachRouteAndClassOnce(self):
        cases = self.cases()
        plan = shards.planShards(cases)
        expected = [testName(case, class_id) for case in cases for class_id in PLAYER_CLASSES]
        shards.validatePartition(expected, plan)
        self.assertEqual(8, len(plan))
        self.assertEqual(plan, shards.planShards(tuple(reversed(cases))))
        weights = shards.caseWeights(cases)
        self.assertLessEqual(max(sum(weights[name] for name in group) for group in plan), 1400)

    def testPartitionsRejectOmissionsDuplicatesAndEmptyGroups(self):
        for plan in ((["a"],), (["a", "b", "b"],), (["a", "b"], [])):
            with self.subTest(plan=plan), self.assertRaises(ValueError):
                shards.validatePartition(["a", "b"], plan)

    def testPlansRejectInvalidWeightsAndCounts(self):
        case = self.cases()[0]
        for duration in (0, -1, float("nan"), float("inf")):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                shards.planShards((replace(case, duration_seconds=duration),))
        for count in (0, -1, 6):
            with self.subTest(count=count), self.assertRaises(ValueError):
                shards.planShards((case,), shard_count=count)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            shards.planShards((case, case))
        with self.assertRaisesRegex(ValueError, "empty"):
            shards.planShards(())

    def testHostedMatrixLimitsKeepTheCompleteUnionAndRejectUnboundedRoutes(self):
        cases = tuple(replace(self.cases()[0], id=f"route_{index}") for index in range(300))
        plan = shards.planShards(cases)
        self.assertEqual(shards.MAX_MATRIX_SHARDS, len(plan))
        shards.validatePartition(shards.caseWeights(cases), plan)
        with self.assertRaisesRegex(ValueError, "hosted job timeout"):
            shards.matrix((replace(self.cases()[0], duration_seconds=7200),))

    def testCatalogMatrixAndSelectorsAgree(self):
        from tests.gameplay_branch_catalog import selectedTestNames

        cases = shards.selectedCases()
        all_names = selectedTestNames()
        shards.validatePartition(all_names, shards.planShards(cases))
        matrix = shards.matrix(cases)["include"]
        self.assertEqual(list(range(len(matrix))), [item["shard"] for item in matrix])
        self.assertTrue(all(item["count"] == len(matrix) for item in matrix))
        for class_id in PLAYER_CLASSES:
            self.assertEqual(
                set(selectedTestNames(class_id=class_id)), set(shards.caseWeights(shards.selectedCases(class_id)))
            )
        for group in {case.group for case in cases}:
            self.assertEqual(
                set(selectedTestNames(group=group)), set(shards.caseWeights(shards.selectedCases(group=group)))
            )
        with self.assertRaisesRegex(ValueError, "Unknown player class"):
            shards.selectedCases("inventedClass")
        with self.assertRaisesRegex(ValueError, "Unknown branch group"):
            shards.selectedCases(group="invented_group")

    def testRuntimeBundleContainsCopiedResourcesAndSameHeadBinaries(self):
        with tempfile.TemporaryDirectory(prefix="nouraajd-mcp-runtime-", dir=shards.ROOT) as temporary:
            root = Path(temporary)
            build = root / "build"
            files = {
                "Release/_game.cp312-win_amd64.pyd": b"extension",
                "Release/game_core.dll": b"core",
                "plugins/native/native_gameplay.dll": b"plugin",
                "config/monsters.json": b"{}",
                "maps/test/map.json": b"{}",
                "save/precious.json": b"save",
                "CMakeFiles/engine.obj": b"intermediate",
                "plugins/__pycache__/script.pyc": b"bytecode",
            }
            files.update(self.runtimeModules())
            for name, data in files.items():
                destination = build / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
            archive_path = root / "runtime.tar.gz"
            shards.bundleRuntime(build, archive_path, "same-head")
            destination = root / "runtime"
            shards.unpackRuntime(archive_path, destination, "same-head")
            self.assertEqual(b"core", (destination / "Release/game_core.dll").read_bytes())
            self.assertEqual(b"plugin", (destination / "plugins/native/native_gameplay.dll").read_bytes())
            manifest = json.loads((destination / shards.MANIFEST_NAME).read_text())
            self.assertEqual("same-head", manifest["head"])
            self.assertFalse((destination / "save").exists())
            self.assertFalse((destination / "CMakeFiles").exists())
            self.assertFalse((destination / "plugins/__pycache__").exists())
            with self.assertRaisesRegex(ValueError, "not built from"):
                shards.unpackRuntime(archive_path, root / "wrong-head", "other-head")
            with self.assertRaisesRegex(ValueError, "empty build"):
                shards.unpackRuntime(archive_path, destination, "same-head")

    def testRuntimeRootResourcesCoverTheCmakeAuthoredModules(self):
        cmake = (shards.ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        authored = {target for source, target in re.findall(r"configure_file\(\s*(res/[^/\s]+)\s+([^/\s)]+)", cmake)}
        self.assertEqual({"game.py", "ui.py", "campaign.py", "narrative.py"}, authored)
        self.assertEqual(authored | {"game_diagnostics.py", "quest_state.py"}, set(shards.ROOT_RESOURCE_FILES))

    def testRuntimeBundlePreservesRootModulesAndExcludesUnrelatedRootArtifacts(self):
        from tests.test_gameplay_branches_mcp import verifyCopiedSources

        for prefix in ("", "Release"):
            with self.subTest(layout=prefix or "flat"), tempfile.TemporaryDirectory(
                prefix="nouraajd-mcp-root-modules-", dir=shards.ROOT
            ) as temporary:
                root = Path(temporary)
                build = root / "build"
                required = {
                    **self.runtimeModules(prefix),
                    (Path(prefix) / "_game.so").as_posix(): b"extension",
                    "config/monsters.json": b"{}",
                    "maps/test/map.json": b"{}",
                    "plugins/example.py": b"plugin",
                }
                rejected = ("obsolete_runtime.py", "mcp.py", "test.py", "play.py", "scratch.json", "engine.obj")
                for name, data in {**required, **dict.fromkeys(rejected, b"not runtime resources")}.items():
                    path = build / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                archive_path = root / "runtime.tar.gz"
                shards.bundleRuntime(build, archive_path, "same-head")
                extracted = root / "extracted"
                shards.unpackRuntime(archive_path, extracted, "same-head")
                manifest = json.loads((extracted / shards.MANIFEST_NAME).read_text())
                self.assertEqual("same-head", manifest["head"])
                self.assertEqual(set(required), set(manifest["files"]))
                for name, data in required.items():
                    self.assertEqual(data, (extracted / name).read_bytes())
                    self.assertEqual(hashlib.sha256(data).hexdigest(), manifest["files"][name])
                for name in rejected:
                    self.assertFalse((extracted / name).exists(), name)
                verifyCopiedSources(
                    str(extracted),
                    prefix or None,
                    tuple("res/" + name for name in ("game.py", "ui.py", "campaign.py", "narrative.py")),
                )

    def testRuntimeBundleRejectsMissingRequiredModulesBeforeCreatingArchive(self):
        for prefix in ("", "Release"):
            for missing in ("narrative.py", "game_diagnostics.py", "quest_state.py"):
                with self.subTest(layout=prefix or "flat", missing=missing), tempfile.TemporaryDirectory(
                    prefix="nouraajd-mcp-incomplete-runtime-", dir=shards.ROOT
                ) as temporary:
                    root = Path(temporary)
                    build = root / "build"
                    files = {
                        **self.runtimeModules(prefix),
                        (Path(prefix) / "_game.so").as_posix(): b"extension",
                        "config/monsters.json": b"{}",
                        "maps/test/map.json": b"{}",
                        "plugins/example.py": b"plugin",
                    }
                    del files[(Path(prefix) / missing).as_posix()]
                    for name, data in files.items():
                        path = build / name
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(data)
                    archive_path = root / "runtime.tar.gz"
                    with self.assertRaisesRegex(ValueError, "Required copied runtime modules.*" + re.escape(missing)):
                        shards.bundleRuntime(build, archive_path, "same-head")
                    self.assertFalse(archive_path.exists())

    def testRuntimeExtractionRejectsTraversalAndLinks(self):
        with tempfile.TemporaryDirectory(prefix="nouraajd-mcp-archive-", dir=shards.ROOT) as temporary:
            root = Path(temporary)
            for index, name in enumerate(("../escape", "/absolute", "C:/escape", "back\\slash", "./alias", "link")):
                archive_path = root / f"unsafe-{index}.tar.gz"
                with tarfile.open(archive_path, "w:gz") as archive:
                    member = tarfile.TarInfo(name)
                    if name == "link":
                        member.type = tarfile.SYMTYPE
                        member.linkname = "outside"
                    else:
                        member.size = 1
                    archive.addfile(member, io.BytesIO(b"x"))
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, "Unsafe"):
                    shards.unpackRuntime(archive_path, root / f"destination-{index}", "head")

    def testInstalledWindowsRuntimeRetainsDependentDllsInFlatLayout(self):
        with tempfile.TemporaryDirectory(prefix="nouraajd-mcp-installed-", dir=shards.ROOT) as temporary:
            root = Path(temporary)
            installed = root / "installed" / "fall-of-nouraajd"
            files = {
                "_game.cp312-win_amd64.pyd": b"extension",
                "game_core.dll": b"core",
                "SDL2.dll": b"sdl",
                "SDL2_image.dll": b"image",
                "SDL2_ttf.dll": b"ttf",
                "libpng16.dll": b"transitive dependency",
                "plugins/native/native_gameplay.dll": b"plugin",
                "config/monsters.json": b"{}",
                "maps/test/map.json": b"{}",
            }
            files.update(self.runtimeModules())
            for name, data in files.items():
                destination = installed / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
            archive_path = root / "runtime.tar.gz"
            shards.bundleRuntime(installed, archive_path, "same-head")
            destination = root / "runtime"
            shards.unpackRuntime(archive_path, destination, "same-head")
            manifest = json.loads((destination / shards.MANIFEST_NAME).read_text())
            self.assertEqual(set(files), set(manifest["files"]))
            for name, data in files.items():
                self.assertEqual(data, (destination / name).read_bytes())
            self.assertFalse((destination / "Release").exists())

    def testRuntimeExtractionRejectsChangedBinary(self):
        with tempfile.TemporaryDirectory(prefix="nouraajd-mcp-checksum-", dir=shards.ROOT) as temporary:
            root = Path(temporary)
            archive_path = root / "changed.tar.gz"
            manifest = {"head": "head", "files": {"_game.so": "incorrect"}}
            with tarfile.open(archive_path, "w:gz") as archive:
                for name, data in (("_game.so", b"changed"), (shards.MANIFEST_NAME, json.dumps(manifest).encode())):
                    member = tarfile.TarInfo(name)
                    member.size = len(data)
                    archive.addfile(member, io.BytesIO(data))
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                shards.unpackRuntime(archive_path, root / "destination", "head")

    def testCanonicalRunnerSeparatesExhaustiveRoutesFromCoreAndCoverage(self):
        import test as harness

        exhaustive = "GameplayBranchMcpTest.test_route_Warrior"
        helper = "GameplayBranchDriverTest.testBoundedMovement"
        baseline = "DialogueMcpWalkthroughTest.testExistingRoute"
        for suite in ("full", "gameplay", "mcp-branches"):
            self.assertTrue(harness.test_name_matches_suite(exhaustive, suite))
        for suite in ("fast", "gameplay-core", "coverage-safe", "ui"):
            self.assertFalse(harness.test_name_matches_suite(exhaustive, suite))
        for suite in ("fast", "full", "coverage-safe"):
            self.assertTrue(harness.test_name_matches_suite(helper, suite))
        self.assertTrue(harness.test_name_matches_suite(baseline, "gameplay-core"))
        self.assertFalse(harness.test_name_matches_suite(baseline, "mcp-branches"))

    def testCanonicalRunnerValidatesBranchSelectors(self):
        import test as harness

        options, arguments = harness.parseBranchRunnerArgs(
            ["test.py", "--suite", "mcp-branches", "--branch-class=Warrior", "--branch-group", "group", "--jobs", "1"]
        )
        self.assertEqual({"class_id": "Warrior", "group": "group", "shard_index": None, "shard_count": None}, options)
        self.assertEqual(["test.py", "--suite", "mcp-branches", "--jobs", "1"], arguments)
        for arguments in (
            ["test.py", "--branch-class"],
            ["test.py", "--branch-class=wrong"],
            ["test.py", "--branch-shard-index=0"],
            ["test.py", "--branch-shard-index=-1", "--branch-shard-count=2"],
            ["test.py", "--branch-shard-index=2", "--branch-shard-count=2"],
        ):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                harness.parseBranchRunnerArgs(arguments)

    def testCanonicalDiscoveryMatchesCatalogAndImportsHelpersOnce(self):
        import test as harness
        from tests.gameplay_branch_catalog import selectedTestNames

        methods = unittest.defaultTestLoader.getTestCaseNames(harness.GameplayBranchMcpTest)
        names = [f"GameplayBranchMcpTest.{method}" for method in methods]
        self.assertEqual(set(selectedTestNames()), set(names))
        self.assertEqual(len(names), len(set(names)))
        for class_name in (
            "GameplayBranchMcpTest",
            "GameplayBranchCatalogTest",
            "GameplayBranchDriverTest",
            "GameplayBranchJournalsTest",
            "GameplayStartingSaveTest",
            "GameplayCampaignRouteTest",
            "McpTestSeedTest",
            "McpBranchShardsTest",
        ):
            self.assertEqual(harness.__name__, getattr(harness, class_name).__module__)
            self.assertFalse(hasattr(harness, "_" + class_name))
        options = {"class_id": PLAYER_CLASSES[0], "group": None, "shard_index": None, "shard_count": None}
        self.assertEqual(
            list(selectedTestNames(class_id=PLAYER_CLASSES[0])), harness.selectBranchTestNames(names, options)
        )
        with self.assertRaisesRegex(ValueError, "discovery does not match"):
            harness.selectBranchTestNames(names[:-1], options)

    def testWorkflowChangeKeepsStrictValidationAndHumanReview(self):
        from scripts.ci_change_classifier import classifyPaths

        classification = classifyPaths([".github/workflows/build.yml"])
        self.assertTrue(classification.nativeNeeded)
        self.assertTrue(classification.coverageNeeded)
        self.assertTrue(classification.authorityChange)
        self.assertTrue(classification.humanReviewRequired)

    def testWindowsWorkflowStagesDependenciesBeforeBundlingRuntime(self):
        workflow = (shards.ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
        windows = workflow.split("\n  windows:\n", 1)[1].split("\n  mcp-branches-linux:\n", 1)[0]
        stage, bundle = (
            "      - name: Stage complete Windows runtime for MCP branches\n",
            "      - name: Bundle current Windows runtime for MCP branches\n",
        )
        self.assertLess(windows.index(stage), windows.index(bundle))
        stage_source = windows.split(stage, 1)[1].split("      - name:", 1)[0]
        bundle_source = windows.split(bundle, 1)[1].split("      - name:", 1)[0]
        self.assertIn(
            "cmake --install cmake-build-release --config Release --prefix test/mcp-runtime-windows", stage_source
        )
        self.assertIn("%VCPKG_INSTALLED_DIR%\\%VCPKG_TARGET_TRIPLET%\\bin", stage_source)
        self.assertIn("(SDL2.dll SDL2_image.dll SDL2_ttf.dll)", stage_source)
        self.assertIn("--build-dir test/mcp-runtime-windows/fall-of-nouraajd", bundle_source)

    def writeReceipts(self, directory, case):
        from tests.gameplay_branch_driver import caseSeed

        for index, class_id in enumerate(case.classes, start=1):
            value = {
                "case": case.id,
                "class": class_id,
                "race": case.race,
                "initialReputation": case.initial_reputation,
                "head": "current-head",
                "seed": caseSeed(case.id, class_id),
                "status": "passed",
                "requiredBranches": list(case.branches),
                "branches": {
                    branch: {"state": {"hp": 10}, "evidence": {"quest": "completed"}} for branch in case.branches
                },
                "seconds": index * 12.5,
            }
            path = directory / f"{case.id}-{class_id}.receipt.json"
            path.write_text(json.dumps(value), encoding="utf-8")

    def testReceiptAuditRequiresExactPassingUnionAndEmitsMeasuredRouteMaxima(self):
        case = replace(self.cases()[0], classes=PLAYER_CLASSES[:2])
        with tempfile.TemporaryDirectory(prefix="nouraajd-mcp-receipts-", dir=shards.ROOT) as temporary:
            root = Path(temporary)
            self.writeReceipts(root, case)
            result = shards.auditReceipts((case,), root, "linux", "current-head", {"issues": (), "pendingGameplay": {}})
            self.assertEqual(2, result["executionCount"])
            self.assertEqual({case.id: 25.0}, result["routeDurationsSeconds"])
            self.assertEqual(
                {testName(case, PLAYER_CLASSES[0]): 12.5, testName(case, PLAYER_CLASSES[1]): 25.0},
                result["testDurationsSeconds"],
            )
            self.assertFalse(result["reviewed"])
            self.assertEqual("current-head", result["head"])

    def testReceiptAuditRejectsMissingDuplicateAndNonPassingExecutions(self):
        case = replace(self.cases()[0], classes=PLAYER_CLASSES[:1])
        with tempfile.TemporaryDirectory(prefix="nouraajd-mcp-incomplete-", dir=shards.ROOT) as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "Missing case/class"):
                shards.auditReceipts((case,), root, "linux", "current-head")
            self.writeReceipts(root, case)
            path = next(root.glob("*.receipt.json"))
            original = path.read_text(encoding="utf-8")
            duplicate = root / "duplicate.receipt.json"
            duplicate.write_text(original, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate case/class"):
                shards.auditReceipts((case,), root, "linux", "current-head")
            duplicate.unlink()
            for status in ("failed", "skipped", "blocked", None):
                value = json.loads(original)
                value["status"] = status
                path.write_text(json.dumps(value), encoding="utf-8")
                with self.subTest(status=status), self.assertRaisesRegex(ValueError, "Non-passing"):
                    shards.auditReceipts((case,), root, "linux", "current-head")

    def testReceiptAuditRejectsWrongContextAndIncompleteBranchAssertions(self):
        case = replace(self.cases()[0], classes=PLAYER_CLASSES[:1])
        with tempfile.TemporaryDirectory(prefix="nouraajd-mcp-invalid-", dir=shards.ROOT) as temporary:
            root = Path(temporary)
            self.writeReceipts(root, case)
            path = next(root.glob("*.receipt.json"))
            original = path.read_text(encoding="utf-8")
            changes = (
                ("head", "stale-head"),
                ("seed", -1),
                ("class", "unknown"),
                ("race", "unknownRace"),
                ("initialReputation", -9),
                ("requiredBranches", []),
                ("requiredBranches", [*case.branches, *case.branches]),
                ("branches", {}),
                ("branches", {case.branches[0]: {"state": {}}}),
                ("seconds", 0),
                ("seconds", float("nan")),
                ("seconds", True),
            )
            for key, value in changes:
                receipt = json.loads(original)
                receipt[key] = value
                path.write_text(json.dumps(receipt), encoding="utf-8")
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    shards.auditReceipts((case,), root, "windows", "current-head")
            path.write_text(original[:-1] + ',"status":"passed"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate receipt JSON key"):
                shards.auditReceipts((case,), root, "windows", "current-head")

    def testReceiptAuditNeverCreditsPendingAuthoredBranches(self):
        case = self.cases()[0]
        for audit in ({"issues": ("missing callback",)}, {"pendingGameplay": {"unreachable.actor": "blocked"}}):
            with self.subTest(audit=audit), self.assertRaisesRegex(ValueError, "pending branches"):
                shards.auditReceipts((case,), shards.ROOT / "absent-receipts", "linux", "current-head", audit)

    def testSchedulingUsesOnlyReviewedTwoPlatformMeasurements(self):
        with tempfile.TemporaryDirectory(prefix="nouraajd-mcp-measurements-", dir=shards.ROOT) as temporary:
            root = Path(temporary)
            value = {
                "schema": "mcp_branch_timings.v1",
                "reviewed": True,
                "platforms": {
                    "linux": {"routeDurationsSeconds": {"route_0": 15}},
                    "windows": {"routeDurationsSeconds": {"route_0": 20}},
                },
            }
            path = root / "reviewed.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            self.assertEqual({"route_0": 20}, shards.reviewedDurations(path))
            for index, change in enumerate(({"reviewed": False}, {"platforms": {"linux": {}}})):
                invalid = root / f"invalid-{index}.json"
                invalid.write_text(json.dumps({**value, **change}), encoding="utf-8")
                with self.assertRaises(ValueError):
                    shards.reviewedDurations(invalid)
            with patch.object(shards, "reviewedDurations", return_value={"route_0": 20}):
                weights = shards.caseWeights(self.cases())
                self.assertEqual(20, weights[testName(self.cases()[0], PLAYER_CLASSES[0])])
                self.assertEqual(400, weights[testName(self.cases()[1], PLAYER_CLASSES[0])])


if __name__ == "__main__":
    unittest.main()
