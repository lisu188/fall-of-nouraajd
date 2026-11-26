# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import recover_history as recovery


class HistoricalRecoveryTest(unittest.TestCase):
    def testDocumentedReplayRequiresMatchingEvidenceAndPreservesOriginalReadme(self):
        commit = self.commit(
            {"main.cpp" + recovery.MARKER_SUFFIX: self.marker(b"int game;\n"), "README.md": b"Original project notes\n"}
        )
        catalog = recovery.auditHistory(self.repo)
        with recovery.GitObjects(self.repo) as objects:
            _, restoration = recovery.prepareSnapshot(objects, catalog, commit)
        evidence = self.root / "evidence"
        evidence.mkdir()
        report = {
            "sourceCommit": commit,
            "sourceTree": restoration["sourceTree"],
            "restoration": {"restoredFilesFingerprint": "f" * 64},
        }
        (evidence / "verification.json").write_text(json.dumps(report))
        with self.assertRaisesRegex(recovery.RecoveryError, "No matching verified"):
            recovery.replayHistory(self.repo, catalog, evidence_dir=evidence)
        report["restoration"]["restoredFilesFingerprint"] = restoration["restoredFilesFingerprint"]
        (evidence / "verification.json").write_text(json.dumps(report))
        documentation = {"README.md": b"Recovery notes\n", "recovery/startup.png": b"test fixture"}
        with patch("scripts.recovery_readme.snapshotDocumentation", return_value=documentation):
            mapping = recovery.replayHistory(self.repo, catalog, evidence_dir=evidence)
        self.assertTrue(mapping["documentationAttached"])
        recovered = mapping["commitMap"][commit]
        self.assertEqual(
            b"Original project notes\n\n---\n\nRecovery notes\n", self.git("show", recovered + ":README.md")
        )
        self.assertEqual(b"test fixture", self.git("show", recovered + ":recovery/startup.png"))
        self.assertNotIn(recovery.MARKER_SUFFIX.encode(), self.git("ls-tree", "-r", "--name-only", recovered))

    def testOverridesCannotReintroduceRemovalMarkers(self):
        original = self.blob(b"int main() {}\n")
        commit = self.commit({"main.cpp" + recovery.MARKER_SUFFIX: original.encode()})
        overrides = {
            "entries": [
                {
                    "path": "leftover.REMOVED.git-id",
                    "blob": original,
                    "add": True,
                    "provenance": "invalid marker addition",
                }
            ]
        }
        with self.assertRaisesRegex(recovery.RecoveryError, "must not contain BFG"):
            recovery.restoreSnapshot(
                self.repo, recovery.auditHistory(self.repo), commit, self.root / "reintroduced-marker", overrides
            )

    def testSelectedTipCanCheckpointACompletePrefixOfIncompleteHistory(self):
        root = self.commit({"main.cpp" + recovery.MARKER_SUFFIX: self.marker(b"int main() {}\n")})
        child = self.commit({"new.cpp" + recovery.MARKER_SUFFIX: b"f" * 40}, parents=[root])
        catalog = recovery.auditHistory(self.repo)
        with self.assertRaisesRegex(recovery.RecoveryError, "unresolved required"):
            recovery.replayHistory(self.repo, catalog)
        result = recovery.replayHistory(self.repo, catalog, tips=[root])
        self.assertEqual([root], result["selectedOriginalTips"])
        self.assertFalse(result["completeDamagedHistory"])
        self.assertEqual({root}, set(result["commitMap"]))
        self.assertNotIn(child, result["commitMap"])
        self.assertEqual(1, len(result["recoveryRefs"]))
        with self.assertRaisesRegex(recovery.RecoveryError, "damaged commits"):
            recovery.replayHistory(self.repo, catalog, tips=["a" * 40])

    def testInvalidPathTypesFailWithRecoveryError(self):
        for value in (None, 12, {}, []):
            with self.subTest(value=value), self.assertRaises(recovery.RecoveryError):
                recovery.safePath(value)

    def testOldGitWithoutObjectFormatOptionStillReadsSha1Objects(self):
        original = recovery.gitCommand
        blob = self.blob(b"old Git compatibility\n")

        def oldGit(repo_root, *args, **kwargs):
            if args == ("rev-parse", "--show-object-format"):
                return b"--show-object-format\n"
            return original(repo_root, *args, **kwargs)

        with patch.object(recovery, "gitCommand", side_effect=oldGit):
            with recovery.GitObjects(self.repo) as objects:
                self.assertEqual(b"old Git compatibility\n", objects.read(blob, "blob"))

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="nouraajd-history-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        subprocess.run(["git", "init", "--quiet", str(self.repo)], check=True)
        self.environment = {
            **os.environ,
            "GIT_AUTHOR_NAME": "Recovery Test",
            "GIT_AUTHOR_EMAIL": "recovery@example.invalid",
            "GIT_COMMITTER_NAME": "Recovery Test",
            "GIT_COMMITTER_EMAIL": "recovery@example.invalid",
            "GIT_AUTHOR_DATE": "2020-01-01T00:00:00+00:00",
            "GIT_COMMITTER_DATE": "2020-01-01T00:00:00+00:00",
        }

    def git(self, *args, data=None):
        return recovery.gitCommand(self.repo, *args, data=data, env=self.environment)

    def blob(self, content):
        return self.git("hash-object", "-w", "--stdin", data=content).decode().strip()

    def commit(self, files, parents=(), ref="refs/heads/main", message="historical snapshot"):
        entries = {}
        for path, value in files.items():
            mode, content = value if isinstance(value, tuple) else ("100644", value)
            entries[path] = {"mode": mode, "blob": self.blob(content)}
        tree = recovery.writeTree(self.repo, entries)
        arguments = ["commit-tree", tree]
        for parent in parents:
            arguments.extend(["-p", parent])
        oid = self.git(*arguments, data=message.encode() + b"\n").decode().strip()
        if ref:
            self.git("update-ref", ref, oid)
        return oid

    def marker(self, content):
        return self.blob(content).encode() + b"\n"

    def testAuditIsDeterministicAndFrozenRefsExcludeLaterHistory(self):
        commit = self.commit({"engine.cpp" + recovery.MARKER_SUFFIX: self.marker(b"int engine;\n")})
        catalog = recovery.auditHistory(self.repo)
        self.assertEqual(catalog, recovery.auditHistory(self.repo))
        self.assertEqual(1, catalog["summary"]["exactOriginalCount"])
        self.assertEqual([commit], catalog["damagedTips"])
        self.commit({"new.cpp" + recovery.MARKER_SUFFIX: b"f" * 40}, ref="refs/heads/new-history")
        self.assertEqual(catalog, recovery.auditHistory(self.repo, catalog))
        self.assertEqual(2, recovery.auditHistory(self.repo)["summary"]["damagedTreeCount"])

    def testExactRecoveryPreservesExecutableModeWithoutChangingWorktree(self):
        commit = self.commit({"run.sh" + recovery.MARKER_SUFFIX: ("100755", self.marker(b"#!/bin/sh\nexit 0\n"))})
        before = self.git("status", "--porcelain")
        output = self.root / "restored"
        report = recovery.restoreSnapshot(self.repo, recovery.auditHistory(self.repo), commit, output)
        self.assertEqual("complete", report["status"])
        self.assertEqual(b"#!/bin/sh\nexit 0\n", (output / "run.sh").read_bytes())
        self.assertEqual(0o755, (output / "run.sh").stat().st_mode & 0o777)
        self.assertEqual("exactOriginal", report["restored"][0]["method"])
        self.assertEqual(before, self.git("status", "--porcelain"))
        with self.assertRaisesRegex(recovery.RecoveryError, "must be new"):
            recovery.restoreSnapshot(self.repo, recovery.auditHistory(self.repo), commit, output)

    def testExistingFileBeatsMarkerAndRetainsItsMode(self):
        commit = self.commit({"run.py": b"print('intact')\n", "run.py" + recovery.MARKER_SUFFIX: ("100755", b"f" * 40)})
        output = self.root / "collision"
        report = recovery.restoreSnapshot(self.repo, recovery.auditHistory(self.repo), commit, output)
        self.assertEqual(b"print('intact')\n", (output / "run.py").read_bytes())
        self.assertEqual(0o644, (output / "run.py").stat().st_mode & 0o777)
        self.assertEqual("existingFile", report["restored"][0]["method"])

    def testMissingOriginalBlocksRestoreAndReplayBeforeWriting(self):
        commit = self.commit({"engine.cpp" + recovery.MARKER_SUFFIX: b"f" * 40})
        catalog = recovery.auditHistory(self.repo)
        output = self.root / "blocked"
        objects_before = self.git("count-objects", "-v")
        with self.assertRaisesRegex(recovery.RecoveryError, "unresolved required"):
            recovery.restoreSnapshot(self.repo, catalog, commit, output)
        with self.assertRaisesRegex(recovery.RecoveryError, "unresolved required"):
            recovery.replayHistory(self.repo, catalog)
        self.assertFalse(output.exists())
        self.assertEqual(objects_before, self.git("count-objects", "-v"))
        report = recovery.restoreSnapshot(self.repo, catalog, commit, output, allow_incomplete=True)
        self.assertEqual("incomplete", report["status"])
        self.assertEqual("engine.cpp", report["unresolved"][0]["path"])

    def testMalformedPointerNeverBecomesAnEmptySuccess(self):
        commit = self.commit({"main.cpp" + recovery.MARKER_SUFFIX: b"not an object id\n"})
        catalog = recovery.auditHistory(self.repo)
        self.assertEqual(1, catalog["summary"]["malformedVersionCount"])
        with self.assertRaisesRegex(recovery.RecoveryError, "unresolved required"):
            recovery.restoreSnapshot(self.repo, catalog, commit, self.root / "malformed")

    def testGeneratedArtifactsAreInventoriedWithoutInventedBinaries(self):
        commit = self.commit(
            {
                "Game.exe" + recovery.MARKER_SUFFIX: b"e" * 40,
                "Game.pro.user" + recovery.MARKER_SUFFIX: b"f" * 40,
                "Makefile.Debug" + recovery.MARKER_SUFFIX: b"d" * 40,
            }
        )
        catalog = recovery.auditHistory(self.repo)
        self.assertEqual(3, catalog["summary"]["excludedVersionCount"])
        report = recovery.restoreSnapshot(self.repo, catalog, commit, self.root / "without-artifacts")
        self.assertEqual(3, len(report["excluded"]))
        self.assertFalse(list((self.root / "without-artifacts").iterdir()))

    def testReconstructionRequiresVerifiedPayloadAndProvenance(self):
        commit = self.commit({"main.cpp" + recovery.MARKER_SUFFIX: ("100755", b"f" * 40)})
        payload = self.root / "payload.cpp"
        payload.write_bytes(b"int main() { return 0; }\n")
        overrides = {
            "_baseDir": str(self.root),
            "entries": [
                {
                    "path": "main.cpp",
                    "source": "payload.cpp",
                    "sha256": "wrong",
                    "provenance": "API reconstruction",
                }
            ],
        }
        catalog = recovery.auditHistory(self.repo)
        with self.assertRaisesRegex(recovery.RecoveryError, "SHA-256 mismatch"):
            recovery.restoreSnapshot(self.repo, catalog, commit, self.root / "bad-hash", overrides)
        overrides["entries"][0]["sha256"] = hashlib.sha256(payload.read_bytes()).hexdigest()
        report = recovery.restoreSnapshot(self.repo, catalog, commit, self.root / "reconstruction", overrides)
        self.assertEqual(payload.read_bytes(), (self.root / "reconstruction" / "main.cpp").read_bytes())
        self.assertEqual("reconstruction", report["restored"][0]["method"])
        self.assertEqual(0o755, (self.root / "reconstruction" / "main.cpp").stat().st_mode & 0o777)

    def testContextSpecificDonorOverridesAndExactOriginalPriority(self):
        exact = b"int original;\n"
        commit = self.commit(
            {"exact.cpp" + recovery.MARKER_SUFFIX: self.marker(exact), "lost.cpp" + recovery.MARKER_SUFFIX: b"f" * 40}
        )
        catalog = recovery.auditHistory(self.repo)
        first = self.blob(b"int generic;\n")
        specific = self.blob(b"int contextual;\n")
        overrides = {
            "entries": [
                {"path": "exact.cpp", "blob": first, "provenance": "generic donor"},
                {"path": "lost.cpp", "blob": first, "provenance": "generic donor"},
                {"path": "lost.cpp", "blob": specific, "commit": commit, "provenance": "matching era donor"},
            ]
        }
        output = self.root / "context"
        recovery.restoreSnapshot(self.repo, catalog, commit, output, overrides)
        self.assertEqual(exact, (output / "exact.cpp").read_bytes())
        self.assertEqual(b"int contextual;\n", (output / "lost.cpp").read_bytes())

    def testOriginalBlobReconstructionAppliesWhereverThatContentWasRemoved(self):
        lost = "e" * 40
        first = self.commit({"src/a.cpp" + recovery.MARKER_SUFFIX: lost.encode() + b"\n"}, ref="refs/heads/one")
        moved = self.commit({"lib/b.cpp" + recovery.MARKER_SUFFIX: lost.encode() + b"\n"}, ref="refs/heads/two")
        catalog = recovery.auditHistory(self.repo)
        donor, rebuilt, pinned = (self.blob(text) for text in (b"int donor;\n", b"int rebuilt;\n", b"int pinned;\n"))
        tree = next(item["tree"] for item in catalog["commits"] if item["commit"] == first)
        overrides = {
            "entries": [
                {"path": "src/a.cpp", "blob": donor, "tree": tree, "provenance": "unverified donor"},
                {"originalBlob": lost, "blob": rebuilt, "provenance": "verified content reconstruction"},
            ]
        }
        for commit, path in ((first, "src/a.cpp"), (moved, "lib/b.cpp")):
            output = self.root / ("blob-" + commit[:8])
            report = recovery.restoreSnapshot(self.repo, catalog, commit, output, overrides)
            self.assertEqual(b"int rebuilt;\n", (output / path).read_bytes())
            self.assertEqual("verified content reconstruction", report["restored"][0]["provenance"])
        overrides["entries"].append({"path": "src/a.cpp", "blob": pinned, "commit": first, "provenance": "explicit"})
        recovery.restoreSnapshot(self.repo, catalog, first, self.root / "pinned", overrides)
        self.assertEqual(b"int pinned;\n", (self.root / "pinned" / "src/a.cpp").read_bytes())
        survivor = self.commit({"keep.h": b"int header;\n", "other.h": b"int other;\n"}, ref="refs/heads/three")
        catalog = recovery.auditHistory(self.repo)
        repair = {"originalBlob": self.blob(b"int header;\n"), "blob": self.blob(b"int repaired;\n")}
        repair.update({"replaceExisting": True, "provenance": "content-keyed compatibility repair"})
        output = self.root / "repaired"
        report = recovery.restoreSnapshot(self.repo, catalog, survivor, output, {"entries": [repair]})
        self.assertEqual(b"int repaired;\n", (output / "keep.h").read_bytes())
        self.assertEqual(b"int other;\n", (output / "other.h").read_bytes())
        self.assertEqual(["compatibilityRepair"], [item["method"] for item in report["restored"]])
        for invalid in ({"tree": tree}, {"add": True}, {"originalBlob": "not-a-sha"}):
            entry = {"originalBlob": lost, "blob": rebuilt, "provenance": "invalid", **invalid}
            with self.subTest(invalid=invalid), self.assertRaises(recovery.RecoveryError):
                recovery.restoreSnapshot(self.repo, catalog, moved, self.root / "x", {"entries": [entry]})
        duplicate = {"originalBlob": lost, "blob": rebuilt, "provenance": "duplicate"}
        with self.assertRaisesRegex(recovery.RecoveryError, "Duplicate original blob"):
            recovery.restoreSnapshot(self.repo, catalog, moved, self.root / "y", {"entries": [duplicate] * 2})

    def testPathTraversalAndEscapingSymlinksAreRejected(self):
        for path in ("../escape", "/absolute", ".git/config", "foo/../../escape", "foo\\escape", "foo/./bar"):
            with self.subTest(path=path), self.assertRaises(recovery.RecoveryError):
                recovery.safePath(path)
        commit = self.commit({"escape": ("120000", b"../../outside")})
        with self.assertRaisesRegex(recovery.RecoveryError, "Symlink escapes"):
            recovery.restoreSnapshot(self.repo, recovery.auditHistory(self.repo), commit, self.root / "bad-link")
        self.assertFalse((self.root / "bad-link").exists())

    def testPayloadSymlinkCannotEscapeOverrideRoot(self):
        commit = self.commit({"lost.cpp" + recovery.MARKER_SUFFIX: b"f" * 40})
        payload_root = self.root / "payloads"
        payload_root.mkdir()
        outside = self.root / "outside.cpp"
        outside.write_text("secret", encoding="utf-8")
        (payload_root / "escape.cpp").symlink_to(outside)
        overrides = {
            "_baseDir": str(payload_root),
            "entries": [
                {
                    "path": "lost.cpp",
                    "source": "escape.cpp",
                    "sha256": hashlib.sha256(b"secret").hexdigest(),
                    "provenance": "invalid payload",
                }
            ],
        }
        with self.assertRaisesRegex(recovery.RecoveryError, "escapes its catalog"):
            recovery.restoreSnapshot(
                self.repo, recovery.auditHistory(self.repo), commit, self.root / "bad-payload", overrides
            )

    def testReplayPreservesMergeTopologyAndCopiesUndamagedBridges(self):
        root = self.commit({"readme": b"original"})
        marker = self.marker(b"int game;\n")
        damaged = self.commit({"main.cpp" + recovery.MARKER_SUFFIX: marker}, [root])
        bridge = self.commit({"main.cpp": b"int intact;\n"}, [damaged])
        side = self.commit({"side.cpp" + recovery.MARKER_SUFFIX: marker}, [damaged], ref="refs/heads/side")
        merged = self.commit({"main.cpp" + recovery.MARKER_SUFFIX: marker}, [bridge, side])
        modern = self.commit({"modern.cpp": b"int modern;\n"}, [merged])
        catalog = recovery.auditHistory(self.repo)
        self.assertEqual([merged], catalog["damagedTips"])
        refs_before = self.git("for-each-ref")
        result = recovery.replayHistory(self.repo, catalog)
        self.assertEqual(root, result["commitMap"][root])
        self.assertNotEqual(bridge, result["commitMap"][bridge])
        self.assertNotIn(modern, result["commitMap"])
        recovered = result["commitMap"][merged]
        parents = self.git("show", "-s", "--format=%P", recovered).decode().split()
        self.assertEqual([result["commitMap"][bridge], result["commitMap"][side]], parents)
        self.assertIn(f"Recovered-from-commit: {merged}", self.git("show", "-s", "--format=%B", recovered).decode())
        self.assertEqual(refs_before, self.git("for-each-ref"))
        self.assertEqual(result, recovery.replayHistory(self.repo, catalog))

    def testBundleIsSelfContainedAndNeverUpdatesOriginalRefs(self):
        self.commit({"main.cpp" + recovery.MARKER_SUFFIX: self.marker(b"int game;\n")})
        namespace = "refs/heads/recovery/bfg/2026-11-15"
        mapping = recovery.replayHistory(self.repo, recovery.auditHistory(self.repo), ref_namespace=namespace)
        self.assertTrue(all(ref.startswith(namespace + "/") for ref in mapping["recoveryRefs"]))
        refs_before = self.git("for-each-ref")
        bundle = self.root / "history.bundle"
        report = recovery.bundleHistory(self.repo, mapping, bundle)
        self.assertEqual("verified", report["status"])
        self.assertEqual(hashlib.sha256(bundle.read_bytes()).hexdigest(), report["sha256"])
        clone = self.root / "imported"
        subprocess.run(["git", "clone", "--bare", "--quiet", str(bundle), str(clone)], check=True)
        imported_refs = recovery.gitCommand(clone, "for-each-ref", "--format=%(refname)").decode().splitlines()
        self.assertEqual(sorted(mapping["recoveryRefs"]), imported_refs)
        checkout = self.root / "checked-out"
        subprocess.run(["git", "clone", "--quiet", str(bundle), str(checkout)], check=True)
        self.assertEqual(b"int game;\n", (checkout / "main.cpp").read_bytes())
        self.assertEqual(refs_before, self.git("for-each-ref"))

    def testVersionedReplayKeepsEarlierRecoveryRefsAndRejectsUnsafeNamespaces(self):
        commit = self.commit({"main.cpp" + recovery.MARKER_SUFFIX: self.marker(b"int game;\n")})
        original_ref = "refs/heads/recovery/bfg/" + commit
        self.git("update-ref", original_ref, commit)
        catalog = recovery.auditHistory(self.repo)
        refs_before = self.git("for-each-ref")
        first = recovery.replayHistory(self.repo, catalog, ref_namespace="refs/heads/recovery/bfg/v1")
        second = recovery.replayHistory(self.repo, catalog, ref_namespace="refs/heads/recovery/bfg/v2")
        self.assertEqual(first["commitMap"], second["commitMap"])
        self.assertTrue(set(first["recoveryRefs"]).isdisjoint(second["recoveryRefs"]))
        self.assertEqual(refs_before, self.git("for-each-ref"))
        for namespace in ("refs/heads/main", "refs/heads/recovery/bfg/../bad", "refs/heads/recovery/bfg/", "bad ref"):
            with self.subTest(namespace=namespace), patch.object(recovery, "writeTree") as write:
                with self.assertRaises(recovery.RecoveryError):
                    recovery.replayHistory(self.repo, catalog, ref_namespace=namespace)
                write.assert_not_called()

    def testReplayRejectsCatalogThatHidesOrChangesDamagedHistory(self):
        self.commit({"main.cpp" + recovery.MARKER_SUFFIX: self.marker(b"int game;\n")})
        catalog = recovery.auditHistory(self.repo)
        for field, value in (("damaged", False), ("tree", "f" * 40), ("parents", ["e" * 40])):
            altered = copy.deepcopy(catalog)
            altered["commits"][0][field] = value
            with self.subTest(field=field), self.assertRaises(recovery.RecoveryError):
                recovery.replayHistory(self.repo, altered)
        altered = copy.deepcopy(catalog)
        altered["damagedTips"] = []
        with self.assertRaisesRegex(recovery.RecoveryError, "do not cover"):
            recovery.replayHistory(self.repo, altered)

    def testSubmodulePinsAndSafeSymlinksRetainOriginalModes(self):
        module = self.commit({"module.cpp": b"int module;\n"}, ref="refs/heads/module")
        tree = recovery.writeTree(
            self.repo,
            {
                "vendor": {"mode": "160000", "blob": module},
                "target.txt": {"mode": "100644", "blob": self.blob(b"target")},
                "link": {"mode": "120000", "blob": self.blob(b"target.txt")},
            },
        )
        commit = self.git("commit-tree", tree, data=b"submodule and symlink\n").decode().strip()
        self.git("update-ref", "refs/heads/main", commit)
        output = self.root / "with-module"
        report = recovery.restoreSnapshot(self.repo, recovery.auditHistory(self.repo), commit, output)
        self.assertEqual([{"path": "vendor", "commit": module}], report["submodules"])
        self.assertTrue((output / "vendor").is_dir())
        self.assertTrue((output / "link").is_symlink())
        self.assertEqual(b"target", (output / "link").read_bytes())

    def testExplicitCompatibilityAdditionsDoNotSilentlyOverwriteRealFiles(self):
        commit = self.commit({"main.cpp": b"int original;\n"})
        catalog = recovery.auditHistory(self.repo)
        replacement = self.blob(b"int replacement;\n")
        entry = {"path": "main.cpp", "blob": replacement, "provenance": "compatibility"}
        with self.assertRaisesRegex(recovery.RecoveryError, "replaceExisting"):
            recovery.restoreSnapshot(self.repo, catalog, commit, self.root / "bad-overwrite", {"entries": [entry]})
        entry["replaceExisting"] = True
        recovery.restoreSnapshot(self.repo, catalog, commit, self.root / "compatibility", {"entries": [entry]})
        self.assertEqual(b"int replacement;\n", (self.root / "compatibility" / "main.cpp").read_bytes())

    def testAuditCliReusesExistingManifestAndReportsSummary(self):
        self.commit({"main.cpp" + recovery.MARKER_SUFFIX: self.marker(b"int original;\n")})
        catalog = self.root / "catalog.json"
        command = ["audit", "--repo-root", str(self.repo), "--catalog", str(catalog)]
        self.assertEqual(0, recovery.main(command))
        original = catalog.read_bytes()
        self.commit({"new.cpp" + recovery.MARKER_SUFFIX: b"f" * 40}, ref="refs/heads/later")
        self.assertEqual(0, recovery.main(command))
        self.assertEqual(original, catalog.read_bytes())
        self.assertEqual(1, json.loads(original)["summary"]["damagedCommitCount"])


class RecoveredPythonIndentationTest(unittest.TestCase):
    def testGateChecksPinnedLibraryBytesAndIndentsOtherSources(self):
        import test as harness

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archived = Path("recovery/upstream/libraries/archive/donor.py")
            unlisted = archived.with_name("independent.py")
            active = Path("scripts/donor.py")
            same_bytes = b"if True:\n\tpass\n"
            for relative in (archived, unlisted, active):
                (root / relative.parent).mkdir(parents=True, exist_ok=True)
                (root / relative).write_bytes(same_bytes)
            entries = [
                {
                    "source": archived.relative_to("recovery").as_posix(),
                    "sha256": hashlib.sha256(same_bytes).hexdigest(),
                }
            ]
            (root / "recovery/overrides.json").write_text(json.dumps({"entries": entries}), encoding="utf-8")
            case = harness.GameTest("test_indentation")
            with (
                patch.object(harness, "REPO_ROOT", root),
                patch.object(harness, "TEST_OUTPUT_DIR", root / "results"),
                patch.object(harness, "git_tracked_files") as tracked,
            ):
                tracked.return_value = [archived.as_posix()]
                case.test_indentation()
                (root / archived).write_bytes(b"if True:\n    pass\n")
                with self.assertRaisesRegex(AssertionError, "sha256"):
                    case.test_indentation()
                for relative in (unlisted, active):
                    with self.subTest(relative=relative):
                        tracked.return_value = [relative.as_posix()]
                        with self.assertRaisesRegex(AssertionError, r"\.py:2"):
                            case.test_indentation()


if __name__ == "__main__":
    unittest.main()
