#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Interactive workbench for content-keyed reconstruction of BFG-damaged history.

Trees are addressed by their position in the catalog's topological order (``1`` is the
2013 root) or by any commit name. Working reconstructions live in ``WORK/recon/<blob>``,
named by the original Git blob that BFG removed, so one reconstruction applies to every
tree that contained that exact original file. Typical loop::

    history_workbench.py prep 13          # restore with current overrides into WORK/src
    history_workbench.py carry 13         # seed missing files from earlier reconstructions
    history_workbench.py build 13         # compile in the pinned toolchain image
    history_workbench.py keep 13 creatures/creature.cpp --note "adapted from ..."
    history_workbench.py verify 13        # real build and isolated startup
    history_workbench.py auto 13 40       # carry/build/keep until the first failure
    history_workbench.py save && history_workbench.py export

``save`` moves working reconstructions into ``recovery/payloads/reconstructions`` and
records them in ``recovery/overrides.json``; ``export`` copies matching successful
evidence into ``recovery/evidence/<commit>``.

Set ``HISTORY_TOOLCHAIN_ROOTFS`` to a rootfs materialized by ``history_rootfs.py``
to use bwrap locally. Source and Git inputs remain read-only; writable inputs and
outputs stay under ``HISTORY_WORK_DIR``. Docker remains the default runner.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import recover_history as rh  # noqa: E402
import history_rootfs as hr  # noqa: E402
import verify_history as vh  # noqa: E402

WORK = Path(os.environ.get("HISTORY_WORK_DIR", REPO / ".cache/history-recovery/workbench")).resolve()
RECON = WORK / "recon"
NOTES = RECON / "notes.json"
IMAGE = os.environ.get("HISTORY_TOOLCHAIN_IMAGE", "nouraajd-recovery:qt5")
ROOTFS = Path(os.environ["HISTORY_TOOLCHAIN_ROOTFS"]).resolve() if os.environ.get("HISTORY_TOOLCHAIN_ROOTFS") else None
CODE = (".cpp", ".h", ".c", ".inl", ".pri", ".qrc")
BLOB = re.compile(r"[0-9a-f]{40}\Z")
CATALOG = json.loads((REPO / "recovery/catalog.json").read_text())
TREE_OF = {commit: tree for tree in CATALOG["trees"] for commit in tree["commits"]}
ORDER = [item["commit"] for item in CATALOG["commits"] if item["commit"] in TREE_OF]


def resolve(ref: str) -> str:
    if ref.isdigit():
        return ORDER[int(ref) - 1]
    return subprocess.check_output(["git", "-C", str(REPO), "rev-parse", ref], text=True).strip()


def missing(commit: str) -> list[dict]:
    return [entry for entry in TREE_OF[commit]["entries"] if entry["status"] == "missingOriginal"]


def workingReconstructions() -> list[Path]:
    RECON.mkdir(parents=True, exist_ok=True)
    return sorted(path for path in RECON.iterdir() if BLOB.fullmatch(path.name))


def reconstructed(blob: str) -> bool:
    """True when a content-keyed reconstruction exists, either working or committed."""
    if (RECON / blob).exists():
        return True
    entries = json.loads((REPO / "recovery/overrides.json").read_text())["entries"]
    return any(entry.get("originalBlob") == blob for entry in entries)


def notes() -> dict:
    return json.loads(NOTES.read_text()) if NOTES.exists() else {}


def note(blob: str, text: str) -> None:
    values = notes()
    values[blob] = text
    NOTES.write_text(json.dumps(values, indent=1, sort_keys=True) + "\n")


def workbenchOverrides() -> Path:
    """Keep a self-contained, pinned input set under the writable work directory."""
    committed = json.loads((REPO / "recovery/overrides.json").read_text())
    working = {path.name: path for path in workingReconstructions()}
    inputs = WORK / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    entries = []
    for entry in committed["entries"]:
        if entry.get("originalBlob") in working:
            continue
        entry = dict(entry)
        if "source" in entry:
            source = (REPO / "recovery" / rh.safePath(entry["source"])).resolve()
            if not source.is_relative_to(REPO / "recovery"):
                raise ValueError("Committed recovery payload escapes its source directory")
            data = source.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if digest != entry.get("sha256"):
                raise ValueError("Committed recovery payload differs from its SHA-256 pin")
            target = inputs / digest
            if target.is_symlink() or (target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != digest):
                raise ValueError("Staged recovery input differs from its SHA-256 pin")
            if not target.exists():
                target.write_bytes(data)
            entry["source"] = target.relative_to(WORK).as_posix()
        entries.append(entry)
    for blob, path in working.items():
        entries.append(
            {
                "originalBlob": blob,
                "source": path.relative_to(WORK).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "provenance": "working reconstruction",
            }
        )
    path = WORK / "overrides.json"
    path.write_text(json.dumps({"schemaVersion": 1, "entries": entries}))
    return path


def docker(command: str, workdir: Path, timeout: float = 3600) -> subprocess.CompletedProcess:
    read_only = hr.gitReadMounts(REPO)
    if ROOTFS is not None:
        return hr.runRootfs(
            ROOTFS,
            ["/bin/bash", "-c", command],
            workdir,
            read_only,
            [WORK],
            environment={"PATH": "/usr/lib/x86_64-linux-gnu/qt5/bin:/usr/bin:/bin"},
            timeout=timeout,
        )
    image_id = subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", IMAGE], text=True).strip()
    arguments = ["docker", "run", "--rm", "--network", "none"]
    arguments += ["-e", "PATH=/usr/lib/x86_64-linux-gnu/qt5/bin:/usr/bin:/bin"]
    arguments += ["-e", "GAME_RECOVERY_TOOLCHAIN_ID=" + image_id]
    for path in read_only:
        arguments += ["-v", f"{path}:{path}:ro"]
    arguments += ["-v", f"{WORK}:{WORK}", "-w", str(workdir)]
    arguments += ["--entrypoint", "bash", IMAGE, "-c", command]
    return subprocess.run(arguments, timeout=timeout, capture_output=True, text=True)


def prep(ref: str, quiet: bool = False) -> Path:
    commit = resolve(ref)
    destination = WORK / "src" / commit[:8]
    shutil.rmtree(destination, ignore_errors=True)
    report = rh.restoreSnapshot(REPO, CATALOG, commit, destination, rh.loadOverrides(workbenchOverrides()))
    if not quiet:
        working = {path.name for path in workingReconstructions()}
        for item in report["restored"]:
            if item["method"] == "reconstruction" and item["path"].endswith(CODE + (".pro", ".py", ".json")):
                marker = "WORK " if item["originalBlob"] in working else "     "
                provenance = str(item["provenance"])[:70]
                print(f"{item['originalBlob'][:10]} {marker}{item['path']}  [{provenance}]")
        print(destination)
    return destination


def carry(ref: str) -> list[tuple[str, str, str]]:
    """Seed missing code from the reconstruction of the nearest earlier version of the same path."""
    commit = resolve(ref)
    source = WORK / "src" / commit[:8]
    working = {path.name for path in workingReconstructions()}
    committed = {
        entry["originalBlob"]: REPO / "recovery" / entry["source"]
        for entry in json.loads((REPO / "recovery/overrides.json").read_text())["entries"]
        if "originalBlob" in entry and "source" in entry
    }

    def content(blob: str) -> bytes | None:
        if blob in working:
            return (RECON / blob).read_bytes()
        return committed[blob].read_bytes() if blob in committed else None

    carried = []
    index = ORDER.index(commit)
    for entry in missing(commit):
        if not entry["path"].endswith(CODE) or content(entry["originalBlob"]) is not None:
            continue
        donor = next(
            (
                earlier["originalBlob"]
                for previous in reversed(ORDER[:index])
                for earlier in missing(previous)
                if earlier["path"] == entry["path"] and content(earlier["originalBlob"]) is not None
            ),
            None,
        )
        if donor:
            (source / entry["path"]).write_bytes(content(donor))
            print("carried", entry["path"], "from", donor[:10])
            carried.append((entry["path"], entry["originalBlob"], donor))
        elif not entry["path"].startswith("json/"):
            print("no earlier reconstruction for", entry["path"])
    return carried


def build(ref: str, clean: bool = True, lines: int = 40) -> bool:
    commit = resolve(ref)
    source = WORK / "src" / commit[:8]
    output = WORK / "build" / commit[:8]
    if clean:
        shutil.rmtree(output, ignore_errors=True)
    output.mkdir(parents=True, exist_ok=True)
    projects = vh.selectProjects(source)
    recipe = vh.selectRecipe(vh.loadRecipes(REPO / "recovery/toolchains/qt5.json"), source, None)
    aliases = vh.prepareLibraryAliases(source, output)
    environment = ["env", *(name + "=" + str(value) for name, value in recipe.get("environment", {}).items())]
    commands = ["set -e"]
    if vh.source_prep.preparationRequired(source):
        commands.append(
            shlex.join(
                [
                    hr.CONTROLLER,
                    str(REPO / "scripts/history_source_prep.py"),
                    "--source-root",
                    str(source),
                    "--output-dir",
                    str(output / "preparation"),
                    "--recipes",
                    str(REPO / "recovery/toolchains/qt5.json"),
                    "--recipe",
                    recipe["id"],
                ]
            )
        )
    for project in [*projects["dependencies"], projects["application"]]:
        build_root = output / project.relative_to(source).parent
        build_root.mkdir(parents=True, exist_ok=True)
        configure = [
            *environment,
            recipe.get("qmakeCommand", "qmake"),
            str(project),
            "-o",
            str(build_root / "Makefile"),
            *recipe.get("qmakeArguments", []),
        ]
        if aliases["aliases"]:
            configure += ["-after", "LIBS+=-L" + aliases["directory"]]
        make = [*environment, recipe.get("makeCommand", "make"), "-k", f"-j{os.cpu_count() or 1}"]
        commands += [
            "cd " + shlex.quote(str(build_root)),
            shlex.join(configure) + ' > qmake.log 2>&1 || { rc=$?; cat qmake.log; exit "$rc"; }',
            shlex.join(make)
            + " > make.log 2>&1 || { rc=$?; "
            + f"grep -E 'error|undefined reference' make.log | sort | uniq | head -{int(lines)}; "
            + 'exit "$rc"; }',
        ]
    result = docker("\n".join(commands), output)
    print(result.stdout, end="")
    return result.returncode == 0


def intactProject(commit: str, name: str) -> tuple[str, str] | None:
    """The nearest commit (by catalog order) whose qmake project survived, and its text."""
    index = ORDER.index(commit) if commit in ORDER else 0
    lost = lambda candidate: any(entry["path"] == name for entry in missing(candidate))  # noqa: E731
    for distance in range(1, len(ORDER)):
        for candidate in (index - distance, index + distance):
            if 0 <= candidate < len(ORDER) and not lost(ORDER[candidate]):
                text = subprocess.run(
                    ["git", "-C", str(REPO), "show", f"{ORDER[candidate]}:{name}"], capture_output=True, text=True
                )
                if text.returncode == 0:
                    return ORDER[candidate], text.stdout
    return None


def project(ref: str) -> str:
    """Write a qmake project from the tree's surviving object_script listing and the nearest intact project."""
    commit = resolve(ref)
    source = WORK / "src" / commit[:8]
    lost = [entry["path"] for entry in missing(commit) if entry["path"].endswith(".pro")]
    if not lost:
        raise SystemExit("this tree's qmake project survived")
    name = lost[0]
    scripts = sorted(source.glob("object_script.*.Debug")) or sorted(source.glob("object_script.*.Release"))
    if not scripts:
        raise SystemExit("no object_script listing survives in this tree")
    objects = [
        Path(line.strip().replace("\\", "/")).stem
        for line in scripts[0].read_text(errors="replace").splitlines()
        if line.strip().endswith(".o")
    ]
    files = [path.relative_to(source).as_posix() for path in source.rglob("*") if path.is_file()]
    by_stem: dict[str, list[str]] = {}
    for path in files:
        if path.endswith((".cpp", ".c", ".cc")):
            by_stem.setdefault(Path(path).stem, []).append(path)
    sources, unknown = [], []
    for stem in objects:
        if stem.startswith(("moc_", "qrc_")):
            continue
        matches = by_stem.get(stem, [])
        (sources.append(matches[0]) if len(matches) == 1 else unknown.append(stem))
    headers = sorted(path for path in files if path.endswith(".h") and not path.startswith("tmp/"))
    donor, template = intactProject(commit, name)
    head = template.split("SOURCES", 1)[0].rstrip()
    lines = [
        head,
        "",
        "SOURCES += " + " \\\n    ".join(sources),
        "",
        "HEADERS  += \\\n    " + " \\\n    ".join(headers),
        "",
    ]
    resources = sorted(path for path in files if path.endswith(".qrc"))
    if resources:
        lines += ["RESOURCES += \\\n    " + " \\\n    ".join(resources), ""]
    (source / name).write_text("\n".join(lines))
    summary = f"{len(sources)} sources from {scripts[0].name}; settings from intact {donor[:8]}:{name}"
    print("wrote", name, "-", summary, "; unmatched objects:", unknown)
    return summary


def keep(ref: str, paths: list[str], text: str | None) -> None:
    commit = resolve(ref)
    blobs = {entry["path"]: entry["originalBlob"] for entry in missing(commit)}
    for path in paths:
        if path not in blobs:
            raise SystemExit("not a missing file in this tree: " + path)
        (RECON / blobs[path]).write_bytes((WORK / "src" / commit[:8] / path).read_bytes())
        if text:
            note(blobs[path], text)
        print("kept", blobs[path][:10], path)


def verify(ref: str, recipe: str | None = None) -> str:
    commit = resolve(ref)
    overrides = workbenchOverrides()
    output = WORK / "verify"
    extra = f"--recipe {recipe}" if recipe else ""
    result = docker(
        f"/opt/recovery/controller/bin/python3.12 {REPO}/scripts/verify_history.py --commit {commit} "
        f"--overrides {overrides} --output-dir {output} --timeout 60 --jobs {os.cpu_count() or 1} {extra} > /dev/null; "
        f"/opt/recovery/controller/bin/python3.12 -c 'import json,sys; "
        f'r=json.load(open(sys.argv[1]))["results"][-1]; print(r["status"], r.get("reason",""))\' '
        f"{output}/summary-0.json",
        REPO,
    )
    print(result.stdout.strip() or result.stderr[-2000:])
    return result.stdout.split(" ", 1)[0]


def accepted(commit: str) -> bool:
    """True when exported success evidence still matches this commit's current restored inputs."""
    report_path = REPO / "recovery/evidence" / commit / "verification.json"
    if not report_path.is_file():
        return False
    report = json.loads(report_path.read_text())
    if report.get("status") != "success":
        return False
    overrides = rh.loadOverrides(workbenchOverrides())
    with rh.GitObjects(REPO) as objects:
        try:
            current = rh.prepareSnapshot(objects, CATALOG, commit, overrides)[1]["restoredFilesFingerprint"]
        except rh.RecoveryError:
            return False
    return report.get("restoration", {}).get("restoredFilesFingerprint") == current


def regeneratedProject(number: int) -> str | None:
    try:
        return project(str(number))
    except SystemExit as reason:
        print("keeping the existing project proposal:", reason)
        return None


def auto(start: int, end: int, check: bool = False) -> None:
    for number in range(start, end + 1):
        commit = ORDER[number - 1]
        if accepted(commit):
            print(f"=== #{number} {commit[:8]} already accepted", flush=True)
            continue
        print(f"=== #{number} {commit[:8]}", flush=True)
        prep(str(number), quiet=True)
        carried = carry(str(number))
        generated = [
            (entry["path"], entry["originalBlob"], summary)
            for entry in missing(commit)
            if entry["path"].endswith(".pro") and not reconstructed(entry["originalBlob"])
            for summary in [regeneratedProject(number)]
            if summary
        ]
        if not build(str(number), lines=25):
            print(f"STOP at #{number}")
            return
        for path, blob, donor in carried:
            (RECON / blob).write_bytes((WORK / "src" / commit[:8] / path).read_bytes())
            note(blob, f"carried forward unchanged from the reconstruction of {donor} (previous version of {path})")
        for path, blob, summary in generated:
            (RECON / blob).write_bytes((WORK / "src" / commit[:8] / path).read_bytes())
            note(blob, "qmake project regenerated with " + summary)
        print(f"kept {len(carried) + len(generated)} files for #{number}")
        if check and verify(str(number)) != "success":
            print(f"STOP at #{number}: startup verification failed")
            return


def save() -> None:
    path = REPO / "recovery/overrides.json"
    overrides = json.loads(path.read_text())
    existing = {entry["originalBlob"]: entry for entry in overrides["entries"] if "originalBlob" in entry}
    names = {
        entry["originalBlob"]: entry["path"]
        for tree in CATALOG["trees"]
        for entry in tree["entries"]
        if entry["status"] == "missingOriginal"
    }
    explanations = notes()
    count = 0
    for working in workingReconstructions():
        blob = working.name
        relative = f"payloads/reconstructions/{blob[:2]}/{blob}-{Path(names[blob]).name}"
        target = REPO / "recovery" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        data = working.read_bytes()
        target.write_bytes(data)
        entry = {
            "originalBlob": blob,
            "path": names[blob],
            "source": relative,
            "sha256": hashlib.sha256(data).hexdigest(),
            "provenance": "content reconstruction of the BFG-removed original; "
            + explanations.get(blob, "derived from the neighbouring reconstruction"),
        }
        if blob in existing:
            existing[blob].clear()
            existing[blob].update(entry)
        else:
            overrides["entries"].append(entry)
        working.unlink()
        count += 1
    path.write_text(json.dumps(overrides, indent=2, sort_keys=True) + "\n")
    print("saved", count)


def export() -> None:
    """Copy successful evidence whose restoration matches the current overrides into recovery/evidence."""
    overrides = rh.loadOverrides(workbenchOverrides())
    current: dict[str, str] = {}
    candidates = sorted((WORK / "verify/evidence").glob("*/verification.json"), key=lambda item: item.stat().st_mtime)
    with rh.GitObjects(REPO) as objects:
        for report_path in candidates:
            report = json.loads(report_path.read_text())
            commit = report["sourceCommit"]
            if commit not in current:
                current[commit] = rh.prepareSnapshot(objects, CATALOG, commit, overrides)[1]["restoredFilesFingerprint"]
            if (
                report.get("status") != "success"
                or report["restoration"]["restoredFilesFingerprint"] != current[commit]
            ):
                continue
            target = REPO / "recovery/evidence" / commit
            target.mkdir(parents=True, exist_ok=True)
            for name in (
                "verification.json",
                "startup.json",
                "startup.png",
                "configure.log",
                "startup.log",
                "source-preparation.json",
                "source-preparation.log",
                "supplemental_images.qrc",
                "reflection_registration.h",
                "coordinates_hash.h",
            ):
                if (report_path.parent / name).exists():
                    shutil.copyfile(report_path.parent / name, target / name)
            with gzip.GzipFile(target / "build.log.gz", "wb", mtime=0) as stream:
                stream.write((report_path.parent / "build.log").read_bytes())
            print("exported", commit[:8])


def stale() -> list[str]:
    """Commits with exported success evidence whose current restoration no longer matches it."""
    overrides = rh.loadOverrides(workbenchOverrides())
    result = []
    with rh.GitObjects(REPO) as objects:
        for report_path in sorted((REPO / "recovery/evidence").glob("*/verification.json")):
            report = json.loads(report_path.read_text())
            commit = report.get("sourceCommit")
            if report.get("status") != "success" or commit not in TREE_OF or report_path.parent.name != commit:
                continue
            try:
                current = rh.prepareSnapshot(objects, CATALOG, commit, overrides)[1]["restoredFilesFingerprint"]
            except rh.RecoveryError:
                current = None
            if report.get("restoration", {}).get("restoredFilesFingerprint") != current:
                result.append(commit)
    return result


def revalidate() -> None:
    """Re-verify every previously accepted commit whose restored inputs changed since its evidence."""
    for commit in stale():
        number = ORDER.index(commit) + 1
        print(f"#{number} {commit[:8]}", end=" ", flush=True)
        verify(commit)


def progress() -> None:
    """Summarize committed evidence in recovery/progress.json."""
    path = REPO / "recovery/progress.json"
    previous = json.loads(path.read_text()) if path.exists() else {}
    published = {item["originalCommit"]: item for item in previous.get("snapshots", []) if item.get("published")}
    snapshots = []
    expected_image = os.environ.get("HISTORY_TOOLCHAIN_IMAGE_ID")
    if ROOTFS is not None:
        expected_image = hr.loadMetadata(ROOTFS)["imageId"]
    overrides = rh.loadOverrides(REPO / "recovery/overrides.json")
    with rh.GitObjects(REPO) as objects:
        for report_path in sorted((REPO / "recovery/evidence").glob("*/verification.json")):
            report = json.loads(report_path.read_text())
            commit = report["sourceCommit"]
            image_id = report.get("toolchainImage", "")
            if (
                report.get("status") != "success"
                or report_path.parent.name != commit
                or commit not in TREE_OF
                or report.get("sourceTree") != TREE_OF[commit]["tree"]
                or not isinstance(image_id, str)
                or not hr.IMAGE_ID.fullmatch(image_id)
                or (expected_image is not None and image_id != expected_image)
            ):
                continue
            try:
                current = rh.prepareSnapshot(objects, CATALOG, commit, overrides)[1]["restoredFilesFingerprint"]
            except rh.RecoveryError:
                continue
            if report.get("restoration", {}).get("restoredFilesFingerprint") != current:
                continue
            try:
                startup_mode = vh.verifiedStartupMode(report)
                startup = vh.validateSmokeReport(
                    report_path.parent / "startup.json", report_path.parent, startup_mode, portable=True
                )
                if startup != report.get("smoke", {}).get("startup"):
                    continue
            except vh.VerificationError:
                continue
            if report.get("startupCompatibility") in ("parentReflectionRegistration", "originalCoordinateHash"):
                from recovery_readme import VerificationError as DocumentationError, snapshotDocumentation

                try:
                    snapshotDocumentation(report, report_path.parent)
                except DocumentationError:
                    continue
            item = {
                "originalCommit": commit,
                "originalTree": report["sourceTree"],
                "evidence": report_path.parent.relative_to(REPO).as_posix(),
                "restoredFilesFingerprint": current,
                "toolchainImage": image_id,
                "startupMode": startup_mode,
                "validation": (
                    "build-and-editor-startup-passed" if startup_mode == "editor" else "build-and-startup-passed"
                ),
                "published": False,
            }
            if report.get("startupCompatibility") == "supplementalQtResources":
                item["startupCompatibility"] = "supplementalQtResources"
                item["validation"] = "build-and-startup-with-resource-compatibility-passed"
            if report.get("startupCompatibility") == "parentReflectionRegistration":
                item["startupCompatibility"] = "parentReflectionRegistration"
                item["validation"] = "build-and-startup-with-reflection-compatibility-passed"
            if report.get("startupCompatibility") == "originalCoordinateHash":
                item["startupCompatibility"] = "originalCoordinateHash"
                item["validation"] = "build-and-startup-with-coordinate-hash-compatibility-passed"
            if report.get("startupCompatibility") == "renamedResourceAliases":
                item["startupCompatibility"] = "renamedResourceAliases"
                item["validation"] = "build-and-startup-with-resource-alias-compatibility-passed"
            old = published.get(commit)
            if old and old.get("restoredFilesFingerprint") == current and old.get("toolchainImage") == image_id:
                item.update(published=True, url=old["url"])
            snapshots.append(item)
    order = {commit: index for index, commit in enumerate(ORDER)}
    snapshots.sort(key=lambda item: order.get(item["originalCommit"], len(order)))
    trees = {item["originalTree"] for item in snapshots}
    value = {
        **{
            key: previous[key]
            for key in ("ciStatus", "sourceInputsReadyTreeCount", "toolchainImage")
            if key in previous and key != "toolchainImage"
        },
        "schemaVersion": 1,
        "status": "in-progress",
        "targetCommitCount": len(ORDER),
        "targetTreeCount": len(CATALOG["trees"]),
        "validatedCommitCount": len(snapshots),
        "validatedTreeCount": len(trees),
        "validatedGameCommitCount": sum(item["startupMode"] == "game" for item in snapshots),
        "validatedGameTreeCount": len({item["originalTree"] for item in snapshots if item["startupMode"] == "game"}),
        "validatedEditorCommitCount": sum(item["startupMode"] == "editor" for item in snapshots),
        "validatedEditorTreeCount": len(
            {item["originalTree"] for item in snapshots if item["startupMode"] == "editor"}
        ),
        "publishedCommitCount": sum(1 for item in snapshots if item["published"]),
        "snapshots": snapshots,
    }
    image_ids = sorted({item["toolchainImage"] for item in snapshots})
    if len(image_ids) == 1:
        value["toolchainImage"] = image_ids[0]
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    print(f"{len(snapshots)} validated commits, {len(trees)} trees")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("missing", "prep", "carry", "build", "verify", "project"):
        command = commands.add_parser(name)
        command.add_argument("ref")
        if name == "verify":
            command.add_argument("--recipe")
        if name == "build":
            command.add_argument("--incremental", action="store_true")
            command.add_argument("-n", type=int, default=40)
    command = commands.add_parser("keep")
    command.add_argument("ref")
    command.add_argument("paths", nargs="+")
    command.add_argument("--note")
    command = commands.add_parser("auto")
    command.add_argument("start", type=int)
    command.add_argument("end", type=int)
    command.add_argument("--verify", action="store_true", help="also verify startup after each kept tree")
    commands.add_parser("save")
    commands.add_parser("export")
    commands.add_parser("progress")
    commands.add_parser("revalidate", help="re-verify accepted commits whose restored inputs changed")
    args = parser.parse_args()
    if args.command == "missing":
        for entry in missing(resolve(args.ref)):
            print(entry["originalBlob"][:10], entry["path"])
    elif args.command == "prep":
        prep(args.ref)
    elif args.command == "carry":
        carry(args.ref)
    elif args.command == "project":
        project(args.ref)
    elif args.command == "build":
        raise SystemExit(0 if build(args.ref, not args.incremental, args.n) else 1)
    elif args.command == "verify":
        raise SystemExit(0 if verify(args.ref, args.recipe) == "success" else 1)
    elif args.command == "keep":
        keep(args.ref, args.paths, args.note)
    elif args.command == "auto":
        auto(args.start, args.end, args.verify)
    elif args.command == "save":
        save()
    elif args.command == "progress":
        progress()
    elif args.command == "revalidate":
        revalidate()
    else:
        export()


if __name__ == "__main__":
    main()
