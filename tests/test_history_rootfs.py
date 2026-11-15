# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded image-layer, mount and current-evidence regressions."""

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tarfile
import tempfile
import unittest
from unittest import mock

from scripts import history_rootfs as rootfs
from scripts import history_workbench as workbench
from scripts import recover_history as recovery
from tests import test_history_recovery as fixtures


def layerBytes(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for entry in entries:
            member = tarfile.TarInfo(entry["name"])
            member.type = entry.get("type", tarfile.REGTYPE)
            member.mode = entry.get("mode", 0o755 if member.isdir() else 0o644)
            member.linkname = entry.get("link", "")
            data = entry.get("data", b"")
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    return output.getvalue()


def saveImage(path, layers, *, digests=None, config_name=None):
    config = {
        "os": "linux",
        "architecture": "amd64",
        "rootfs": {
            "type": "layers",
            "diff_ids": digests or ["sha256:" + hashlib.sha256(x).hexdigest() for x in layers],
        },
        "config": {"Env": ["PATH=/usr/bin:/bin", "QT_OPENGL=software"], "Entrypoint": [rootfs.CONTROLLER]},
    }
    raw = json.dumps(config, sort_keys=True).encode()
    image_id = "sha256:" + hashlib.sha256(raw).hexdigest()
    if config_name == "oci":
        config_name = "blobs/sha256/" + image_id.removeprefix("sha256:")
    config_name = config_name or image_id.removeprefix("sha256:") + ".json"
    names = [f"layer{number}/layer.tar" for number in range(len(layers))]
    manifest = json.dumps([{"Config": config_name, "Layers": names, "RepoTags": ["recovery:test"]}]).encode()
    with tarfile.open(path, "w:gz") as archive:
        for name, data in [*zip(names, layers), (config_name, raw), ("manifest.json", manifest)]:
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    return image_id


class HistoryRootfsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="nouraajd-rootfs-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.archive = self.root / "image.tar.gz"
        self.destination = self.root / "rootfs"

    def materialize(self, *layers):
        image_id = saveImage(self.archive, [layerBytes(layer) for layer in layers])
        metadata = rootfs.materializeImage(self.archive, self.destination, image_id)
        self.assertEqual(image_id, metadata["imageId"])
        return metadata

    def testLayersReplaceFilesAndKeepExecutablesAndReadOnlyDirectories(self):
        self.materialize(
            [{"name": "bin", "type": tarfile.DIRTYPE, "mode": 0o555}, {"name": "bin/game", "data": b"old"}],
            [{"name": "bin/game", "data": b"new", "mode": 0o755}],
        )
        self.assertEqual(b"new", (self.destination / "bin/game").read_bytes())
        self.assertEqual(0o755, stat.S_IMODE((self.destination / "bin/game").stat().st_mode))
        self.assertEqual(0o555, stat.S_IMODE((self.destination / "bin").stat().st_mode))
        (self.destination / "bin").chmod(0o755)

    def testWhiteoutsApplyBeforeNewLayerContents(self):
        self.materialize(
            [{"name": "data/old", "data": b"old"}, {"name": "obsolete", "data": b"remove"}],
            [{"name": "data/new", "data": b"new"}, {"name": "data/.wh..wh..opq"}, {"name": ".wh.obsolete"}],
        )
        self.assertEqual(["new"], sorted(path.name for path in (self.destination / "data").iterdir()))
        self.assertFalse((self.destination / "obsolete").exists())
        self.assertFalse(any(path.name.startswith(".wh.") for path in self.destination.rglob("*")))

    def testContainerAbsoluteSymlinkCannotWriteToTheHost(self):
        outside = self.root / "outside"
        outside.mkdir()
        self.materialize(
            [{"name": "alias", "type": tarfile.SYMTYPE, "link": str(outside)}],
            [{"name": "alias/result", "data": b"inside"}],
        )
        self.assertFalse((outside / "result").exists())
        self.assertEqual(b"inside", (self.destination / str(outside).lstrip("/") / "result").read_bytes())

    def testInternalSymlinkAndForwardHardlinkResolveInsideImage(self):
        self.materialize(
            [
                {"name": "usr/bin", "type": tarfile.DIRTYPE},
                {"name": "bin", "type": tarfile.SYMTYPE, "link": "usr/bin"},
                {"name": "bin/alias", "type": tarfile.LNKTYPE, "link": "usr/bin/game"},
                {"name": "usr/bin/game", "data": b"binary", "mode": 0o755},
            ]
        )
        self.assertEqual(b"binary", (self.destination / "bin/alias").read_bytes())
        self.assertEqual(
            (self.destination / "bin/alias").stat().st_ino, (self.destination / "usr/bin/game").stat().st_ino
        )

    def testDeferredDirectoryModesAndHardlinksNeverFollowHostSymlinks(self):
        outside = self.root / "outside"
        outside.mkdir()
        before = stat.S_IMODE(outside.stat().st_mode)
        self.materialize(
            [
                {"name": "swap", "type": tarfile.DIRTYPE, "mode": 0o700},
                {"name": "swap/link", "type": tarfile.LNKTYPE, "link": "file"},
                {"name": "file", "data": b"safe"},
                {"name": "swap", "type": tarfile.SYMTYPE, "link": str(outside)},
            ]
        )
        self.assertEqual([], list(outside.iterdir()))
        self.assertEqual(before, stat.S_IMODE(outside.stat().st_mode))

    def testTraversalAndEscapingRelativeLinksAreRejectedAndPartialOutputRemoved(self):
        entries = [
            {"name": "../escape", "data": b"no"},
            {"name": "/absolute", "data": b"no"},
            {"name": "link", "type": tarfile.SYMTYPE, "link": "../escape"},
            {"name": "link", "type": tarfile.LNKTYPE, "link": "../escape"},
            {"name": rootfs.METADATA, "type": tarfile.SYMTYPE, "link": "/tmp/escape"},
            {"name": "device", "type": tarfile.CHRTYPE},
        ]
        for entry in entries:
            with self.subTest(entry=entry):
                image_id = saveImage(self.archive, [layerBytes([entry])])
                with self.assertRaises(rootfs.RootfsError):
                    rootfs.materializeImage(self.archive, self.destination, image_id)
                self.assertFalse(self.destination.exists())
        self.assertFalse((self.root / "escape").exists())

    def testAliasedProvenanceSymlinkCannotOverwriteAHostFile(self):
        outside = self.root / "outside.json"
        image_id = saveImage(
            self.archive,
            [
                layerBytes(
                    [
                        {"name": "alias", "type": tarfile.SYMTYPE, "link": "."},
                        {"name": "alias/" + rootfs.METADATA, "type": tarfile.SYMTYPE, "link": str(outside)},
                    ]
                )
            ],
        )
        with self.assertRaisesRegex(rootfs.RootfsError, "reserved runner"):
            rootfs.materializeImage(self.archive, self.destination, image_id)
        self.assertFalse(outside.exists())
        self.assertFalse(self.destination.exists())

    def testLayerAndImageIdentityMismatchesAreRejected(self):
        layer = layerBytes([{"name": "file", "data": b"original"}])
        image_id = saveImage(self.archive, [layer], digests=["sha256:" + "0" * 64])
        with self.assertRaisesRegex(rootfs.RootfsError, "layer SHA-256"):
            rootfs.materializeImage(self.archive, self.destination, image_id)
        self.assertFalse(self.destination.exists())
        with self.assertRaisesRegex(rootfs.RootfsError, "recorded toolchain"):
            rootfs.inspectImage(self.archive, "sha256:" + "f" * 64)
        saveImage(self.archive, [layer], config_name="not-the-config-hash.json")
        with self.assertRaisesRegex(rootfs.RootfsError, "config SHA-256"):
            rootfs.inspectImage(self.archive)

    def testModernDockerSaveConfigPathStillVerifiesItsContentHash(self):
        image_id = saveImage(self.archive, [layerBytes([{"name": "file", "data": b"modern"}])], config_name="oci")
        rootfs.materializeImage(self.archive, self.destination, image_id)
        self.assertEqual(b"modern", (self.destination / "file").read_bytes())

    def testPreexistingDestinationAndInsufficientSpaceAreNotModified(self):
        image_id = saveImage(self.archive, [layerBytes([{"name": "file"}])])
        self.destination.mkdir()
        marker = self.destination / "user-work"
        marker.write_bytes(b"keep")
        with self.assertRaisesRegex(rootfs.RootfsError, "already exist"):
            rootfs.materializeImage(self.archive, self.destination, image_id)
        self.assertEqual(b"keep", marker.read_bytes())
        marker.unlink()
        self.destination.rmdir()
        with mock.patch.object(
            rootfs.shutil, "disk_usage", return_value=type("Usage", (), {"total": 100, "used": 99, "free": 1})()
        ):
            with self.assertRaisesRegex(rootfs.RootfsError, "disk headroom"):
                rootfs.materializeImage(self.archive, self.destination, image_id)
        self.assertFalse(self.destination.exists())

    def testRunnerMountsOnlyDeclaredPathsAndClearsDesktopEnvironment(self):
        metadata = self.materialize([{"name": "etc", "type": tarfile.DIRTYPE}])
        source, work = self.root / "source", self.root / "work"
        source.mkdir()
        work.mkdir()
        with mock.patch.object(rootfs.shutil, "which", return_value="/usr/bin/bwrap"):
            command = rootfs.bwrapCommand(
                self.destination,
                ["/bin/true"],
                source,
                [source],
                [work],
                {"GAME_RECOVERY_TOOLCHAIN_ID": "forged-identity"},
            )
            with self.assertRaisesRegex(rootfs.RootfsError, "source checkout"):
                rootfs.bwrapCommand(self.destination, ["/bin/true"], source, [source], [source])
        self.assertIn("--clearenv", command)
        self.assertIn("--unshare-net", command)
        self.assertNotIn("DISPLAY", command)
        self.assertIn(metadata["imageId"], command)
        self.assertNotIn("forged-identity", command)
        self.assertIn(["--ro-bind", str(source), str(source)], [command[n : n + 3] for n in range(len(command) - 2)])
        self.assertIn(["--bind", str(work), str(work)], [command[n : n + 3] for n in range(len(command) - 2)])
        self.assertNotIn(["--bind", "/", "/"], [command[n : n + 3] for n in range(len(command) - 2)])


class HistoryWorkbenchEvidenceTest(unittest.TestCase):
    setUp = fixtures.HistoricalRecoveryTest.setUp
    git = fixtures.HistoricalRecoveryTest.git
    blob = fixtures.HistoricalRecoveryTest.blob
    commit = fixtures.HistoricalRecoveryTest.commit

    def prepareEvidence(self):
        commit = self.commit({"creature.cpp" + recovery.MARKER_SUFFIX: b"f" * 40})
        catalog = recovery.auditHistory(self.repo)
        directory = self.repo / "recovery"
        directory.mkdir()
        self.payload = directory / "payload.cpp"
        self.override = directory / "overrides.json"
        self.setPayload(b"int first;\n")
        overrides = recovery.loadOverrides(self.override)
        with recovery.GitObjects(self.repo) as objects:
            fingerprint = recovery.prepareSnapshot(objects, catalog, commit, overrides)[1]["restoredFilesFingerprint"]
        self.report = directory / "evidence" / commit / "verification.json"
        self.report.parent.mkdir(parents=True)
        self.report.write_text(
            json.dumps(
                {
                    "sourceCommit": commit,
                    "sourceTree": catalog["trees"][0]["tree"],
                    "status": "success",
                    "toolchainImage": "sha256:" + "a" * 64,
                    "restoration": {"restoredFilesFingerprint": fingerprint},
                }
            )
        )
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        for name, value in {
            "REPO": self.repo,
            "WORK": self.root / "work",
            "RECON": self.root / "work/recon",
            "ROOTFS": None,
            "CATALOG": catalog,
            "ORDER": [commit],
            "TREE_OF": {commit: catalog["trees"][0]},
        }.items():
            stack.enter_context(mock.patch.object(workbench, name, value))
        stack.enter_context(mock.patch.dict(os.environ, {}, clear=True))

    def setPayload(self, content):
        self.payload.write_bytes(content)
        self.override.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "entries": [
                        {
                            "originalBlob": "f" * 40,
                            "path": "creature.cpp",
                            "source": "payload.cpp",
                            "sha256": hashlib.sha256(content).hexdigest(),
                            "provenance": "test reconstruction",
                        }
                    ],
                }
            )
        )

    def testPayloadChangeInvalidatesOldSuccessfulEvidenceWithoutDeletingIt(self):
        self.prepareEvidence()
        workbench.progress()
        path = self.repo / "recovery/progress.json"
        self.assertEqual(1, json.loads(path.read_text())["validatedCommitCount"])
        self.setPayload(b"int changed;\n")
        workbench.progress()
        self.assertEqual(0, json.loads(path.read_text())["validatedCommitCount"])
        self.assertTrue(self.report.is_file())

    def testImageIdentityIsRequiredAndMustMatchAnExplicitExpectedImage(self):
        self.prepareEvidence()
        report = json.loads(self.report.read_text())
        for identity in (None, "old local image description", "sha256:" + "b" * 64):
            with self.subTest(identity=identity):
                report["toolchainImage"] = identity
                self.report.write_text(json.dumps(report))
                with mock.patch.dict(os.environ, {"HISTORY_TOOLCHAIN_IMAGE_ID": "sha256:" + "a" * 64}):
                    workbench.progress()
                self.assertEqual(
                    0, json.loads((self.repo / "recovery/progress.json").read_text())["validatedCommitCount"]
                )

    def testWorkbenchStagesPinnedInputsUnderWorkAndKeepsOriginalSourcesUntouched(self):
        self.prepareEvidence()
        before = self.payload.read_bytes()
        first = workbench.workbenchOverrides()
        second = workbench.workbenchOverrides()
        self.assertEqual(first, second)
        self.assertTrue(first.is_relative_to(workbench.WORK))
        self.assertEqual(1, len(list((workbench.WORK / "inputs").iterdir())))
        overrides = recovery.loadOverrides(first)
        staged = Path(overrides["_baseDir"]) / overrides["entries"][0]["source"]
        self.assertEqual(before, staged.read_bytes())
        self.assertEqual(before, self.payload.read_bytes())

    def testWorkbenchSelectsRootfsAndIncludesReadOnlyGitAlternates(self):
        self.prepareEvidence()
        alternate = self.root / "alternate-objects"
        alternate.mkdir()
        (self.repo / ".git/objects/info/alternates").write_text(str(alternate) + "\n")
        result = object()
        with mock.patch.object(workbench, "ROOTFS", self.root / "image"), mock.patch.object(
            workbench.hr, "runRootfs", return_value=result
        ) as run:
            self.assertIs(result, workbench.docker("true", self.repo))
        self.assertIn(alternate, run.call_args.args[3])
        self.assertEqual([workbench.WORK], run.call_args.args[4])
        self.assertEqual(["/bin/bash", "-c", "true"], run.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
