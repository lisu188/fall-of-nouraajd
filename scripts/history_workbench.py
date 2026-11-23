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
import functools
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
# Startup watchdog for verify; trees with genuine minutes-long background loading need more.
VERIFY_TIMEOUT = float(os.environ.get("HISTORY_VERIFY_TIMEOUT", "60"))
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
    methods = {item["path"]: item["method"] for item in report["restored"]}
    record = WORK / "restoration" / f"{commit}.json"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps(methods, indent=1, sort_keys=True))
    if not quiet:
        working = {path.name for path in workingReconstructions()}
        for item in report["restored"]:
            if item["method"] == "reconstruction" and item["path"].endswith(CODE + (".pro", ".py", ".json")):
                marker = "WORK " if item["originalBlob"] in working else "     "
                print(f"{item['originalBlob'][:10]} {marker}{item['path']}  [{item['provenance'][:70]}]")
        print(destination)
    return destination


def survivesInGit(commit: str, path: str) -> bool:
    return subprocess.run(["git", "-C", str(REPO), "cat-file", "-e", f"{commit}:{path}"], capture_output=True).returncode == 0


def earlierReconstruction(path: str, index: int, available, survives=survivesInGit) -> tuple[str, str] | None:
    """The nearest earlier version of ``path``: a reconstruction or a surviving original.

    Walking back from ``index``, the first earlier tree that either has a reconstruction
    for ``path`` or still contains the genuine file wins; a genuine file is returned as
    ``original:<commit>``. Only when no earlier tree has the same path is the nearest
    reconstruction with the same basename (case-insensitively) used, which follows the
    developer's directory moves such as ``creatures/creature.cpp`` ->
    ``src/creatures/creature.cpp`` -> ``src/creature.cpp``. Returns ``(donor, earlierPath)``.
    """
    for previous in reversed(ORDER[:index]):
        for earlier in missing(previous):
            if earlier["path"] == path and available(earlier["originalBlob"]):
                return earlier["originalBlob"], path
        if not any(earlier["path"] == path for earlier in missing(previous)) and survives(previous, path):
            return f"original:{previous}", path
    for previous in reversed(ORDER[:index]):
        for earlier in missing(previous):
            if Path(earlier["path"]).name.lower() == Path(path).name.lower() and available(earlier["originalBlob"]):
                return earlier["originalBlob"], earlier["path"]
    return None


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
        if blob.startswith("original:"):
            return None
        if blob in working:
            return (RECON / blob).read_bytes()
        return committed[blob].read_bytes() if blob in committed else None

    record = WORK / "restoration" / f"{commit}.json"
    if not record.is_file():
        raise SystemExit("run prep first: carry needs this tree's restoration methods")
    methods = json.loads(record.read_text())
    carried = []
    index = ORDER.index(commit)
    for entry in missing(commit):
        if not entry["path"].endswith(CODE) or content(entry["originalBlob"]) is not None:
            continue
        if methods.get(entry["path"]) != "reconstruction":
            continue  # exact originals and compatibility repairs are never replaced by older versions
        found = earlierReconstruction(entry["path"], index, lambda blob: content(blob) is not None)
        if found:
            donor, earlier_path = found
            if donor.startswith("original:"):
                previous = donor.split(":", 1)[1]
                data = subprocess.run(
                    ["git", "-C", str(REPO), "show", f"{previous}:{earlier_path}"], capture_output=True, check=True
                ).stdout
                label = f"surviving original {earlier_path} at {previous[:8]}"
            else:
                data = content(donor)
                moved = "" if earlier_path == entry["path"] else f" (moved from {earlier_path})"
                label = f"reconstruction {donor[:10]}{moved}"
            (source / entry["path"]).write_bytes(data)
            print("carried", entry["path"], "from", label)
            carried.append((entry["path"], entry["originalBlob"], label))
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
    if (
        commit == vh.source_prep.console_prep.COMMIT
        or commit in vh.source_prep.scene_prep.PINS
        or commit == vh.source_prep.panel_prep.COMMIT
        or commit == vh.source_prep.text_shutdown_prep.COMMIT
        or commit == vh.source_prep.sparse_prep.COMMIT
        or commit == vh.source_prep.named_event_prep.COMMIT
        or commit in vh.source_prep.effect_prep.COMMITS
        or commit in vh.source_prep.resources_prep.COMMITS
        or commit in vh.source_prep.import_hook_prep.COMMITS
        or commit in vh.source_prep.map_events_prep.COMMITS
        or commit in vh.source_prep.python_effects_prep.COMMITS
        or commit in vh.source_prep.class_loaders_prep.COMMITS
        or commit in vh.source_prep.map_packages_prep.COMMITS
        or commit in vh.source_prep.potion_movement_prep.COMMITS
        or commit in vh.source_prep.fight_system_prep.COMMITS
        or commit in vh.source_prep.creature_events_prep.COMMITS
        or commit in vh.source_prep.visitor_callbacks_prep.COMMITS
        or commit in vh.source_prep.loader_prep.COMMITS
        or commit in vh.source_prep.panel_refresh_prep.PROFILES
        or commit in vh.source_prep.shutdown_prep.TARGETS
        or commit in (
            vh.source_prep.console_prep.COMMIT, vh.source_prep.trigger_prep.COMMIT, vh.source_prep.position_prep.COMMIT
        )
        or commit in vh.source_prep.merged_prep.COMMITS
        or vh.source_prep.preparationRequired(source)
    ):
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
                    "--source-commit",
                    commit,
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


@functools.lru_cache(maxsize=1)
def committedPayloads() -> dict[str, str]:
    entries = json.loads((REPO / "recovery/overrides.json").read_text())["entries"]
    return {entry["originalBlob"]: entry["source"] for entry in entries if entry.get("originalBlob") and entry.get("source")}


def reconstructionText(blob: str) -> str | None:
    """A working or committed content-keyed reconstruction of ``blob``, if any."""
    if (RECON / blob).exists():
        return (RECON / blob).read_text(errors="replace")
    source = committedPayloads().get(blob)
    if source is None:
        return None
    path = (REPO / "recovery" / rh.safePath(source)).resolve()
    return path.read_text(errors="replace") if path.is_relative_to(REPO / "recovery") else None


def projectTemplates(commit: str, name: str, radius: int = 40) -> list[tuple[str, str, int, str]]:
    """Candidate project settings: the nearest intact project plus nearby reconstructed ones.

    Each candidate is ``(commit, text, distance, kind)``. Reconstructed neighbours matter
    after layout moves (for example sources moving under ``src/`` and ``lib/``), where the
    nearest intact project predates the move and matches none of this tree's files.
    """
    index = ORDER.index(commit) if commit in ORDER else 0
    candidates = []
    intact = intactProject(commit, name)
    if intact is not None:
        candidates.append((intact[0], intact[1], abs(ORDER.index(intact[0]) - index), "intact"))
    for distance in range(1, radius + 1):
        for position in (index - distance, index + distance):
            if not 0 <= position < len(ORDER):
                continue
            for entry in missing(ORDER[position]):
                if entry["path"] == name:
                    text = reconstructionText(entry["originalBlob"])
                    if text is not None:
                        candidates.append((ORDER[position], text, distance, "reconstructed"))
    return candidates


def templateUnits(template: str, files: list[str]) -> list[str]:
    """The project template's SOURCES that exist in this tree, matched case-insensitively."""
    listed = []
    for block in re.findall(r"^[ \t]*SOURCES[ \t]*\+?=((?:.*\\\n)*.*)$", template, flags=re.M):
        for token in block.split():
            token = re.sub(r"^(\$\$PWD/|\./)", "", token.replace("\\", "/"))
            if token.endswith((".cpp", ".c", ".cc")):
                listed.append(token)
    present = sorted(path for path in files if path.endswith((".cpp", ".c", ".cc")) and not path.startswith("tmp/"))
    by_lower = {path.lower(): path for path in present}
    kept: list[str] = []
    for token in listed:
        match = token if token in by_lower.values() else by_lower.get(token.lower())
        if match and match not in kept:
            kept.append(match)
    return kept


def donorSources(template: str, files: list[str], read=None) -> list[str]:
    """Infer a tree's translation units when no object_script listing survives.

    Keeps the donor project's SOURCES that still exist in this tree (matching
    Windows-era paths case-insensitively), then adds this tree's other C/C++ files from
    directories the donor already compiled from. With ``read``, sources of new directories
    reached through ``#include`` closure are added too (see ``includedSources``). The result is an inference, not the
    original list; native build and startup verification decide whether it is accepted.
    """
    present = sorted(path for path in files if path.endswith((".cpp", ".c", ".cc")) and not path.startswith("tmp/"))
    kept = templateUnits(template, files)
    directories = {Path(path).parent.as_posix() for path in kept}
    extra = [
        path
        for path in present
        if path not in kept
        and Path(path).parent.as_posix() in directories
        and not Path(path).name.startswith(("moc_", "qrc_"))
    ]
    units = kept + extra
    if read is not None and units:
        units += includedSources(units, files, present, directories, read)
    return units


INCLUDE = re.compile(r'^[ \t]*#[ \t]*include[ \t]*[<"]([^>"]+)[>"]', re.M)
ENTRY_POINT = re.compile(r"\bint\s+main\s*\(")
COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)


def definesEntryPoint(text: str | None) -> bool:
    """True when ``main`` is declared outside comments (zlib's inflate.c mentions it in one)."""
    return bool(text) and ENTRY_POINT.search(COMMENT.sub(" ", text)) is not None


def includedSources(units: list[str], files: list[str], present: list[str], directories: set[str], read) -> list[str]:
    """Add translation units from directories the inferred units reach through ``#include``.

    Directories introduced after the donor project (for example vendored TMX, TinyXML or
    zlib sources) are otherwise missing at link time. The first reached header in a
    directory the donor did not compile from adds all of that directory's C/C++ sources,
    except generated ``moc_``/``qrc_`` files and files defining ``main``; their includes
    are followed in turn. Includes resolve against the including file's directory, then
    the tree root, case-insensitively as on the original Windows hosts.
    """
    by_lower = {path.lower(): path for path in files}
    by_directory: dict[str, list[str]] = {}
    for path in present:
        if not Path(path).name.startswith(("moc_", "qrc_")):
            by_directory.setdefault(Path(path).parent.as_posix(), []).append(path)
    added: list[str] = []
    entered = set(directories)
    queue, seen = list(units), set(units)
    while queue:
        current = queue.pop()
        text = read(current)
        if not text:
            continue
        for name in INCLUDE.findall(text):
            name = name.replace("\\", "/")
            header = None
            for base in (Path(current).parent.as_posix(), "."):
                candidate = os.path.normpath(f"{base}/{name}").replace(os.sep, "/")
                header = by_lower.get(candidate.lower())
                if header:
                    break
            if header is None or header in seen:
                continue
            seen.add(header)
            queue.append(header)
            directory = Path(header).parent.as_posix()
            if directory in entered:
                continue
            entered.add(directory)
            for path in by_directory.get(directory, []):
                if path not in seen and not definesEntryPoint(read(path)):
                    seen.add(path)
                    queue.append(path)
                    added.append(path)
    return added


QT_KEYWORDS = re.compile(r"^[ \t]*(?:(?:public|protected|private)[ \t]+)?(?:slots|signals)[ \t]*:", re.M)
BOOST_PYTHON_USE = re.compile(r'#[ \t]*include[ \t]*[<"]boost/python')
PYTHON2_API = re.compile(r"\bPy_InitModule\w*\s*\(")
PYTHON_USE = re.compile(r'#[ \t]*include[ \t]*[<"](?:Python\.h|boost/python)')


def adaptSettings(head: str, files: list[str], read) -> tuple[str, list[str]]:
    """Fit settings borrowed from a reconstructed neighbour project to this tree.

    A later neighbour may define ``QT_NO_KEYWORDS`` and link Python because it embeds an
    interpreter; an earlier tree whose headers still use bare ``slots``/``signals`` and
    never includes Python cannot be built with those settings.
    """
    adjustments = []
    code = [path for path in files if path.endswith((".h", ".hpp", ".cpp", ".c")) and not path.startswith("tmp/")]
    if "QT_NO_KEYWORDS" in head and any(QT_KEYWORDS.search(read(path) or "") for path in code if path.endswith((".h", ".hpp"))):
        head = re.sub(r"^([ \t]*DEFINES[ \t]*\+?=.*?)[ \t]*\bQT_NO_KEYWORDS\b", r"\1", head, flags=re.M)
        head = re.sub(r"^[ \t]*DEFINES[ \t]*\+?=[ \t]*$\n?", "", head, flags=re.M)
        adjustments.append("QT_NO_KEYWORDS dropped because this tree uses bare Qt keywords")
    if re.search(r"python3", head, re.I) and any(PYTHON2_API.search(read(path) or "") for path in code):
        head = re.sub(r"-lpython3\.\d+m?", "-lpython2.7", head)
        head = re.sub(r"-lpython3\d+", "-lpython27", head)
        adjustments.append("Python 3 libraries replaced by Python 2.7 because this tree uses the Python 2 module API")
    if "boost_python" not in head and any(BOOST_PYTHON_USE.search(read(path) or "") for path in code):
        library = "-lboost_python3" if re.search(r"-lpython3", head) else "-lboost_python"
        head = head.rstrip() + "\nunix:LIBS += " + library
        adjustments.append(f"{library} added because this tree includes Boost.Python")
    if re.search(r"python", head, re.I) and not any(PYTHON_USE.search(read(path) or "") for path in code):
        head = re.sub(r"^.*LIBS.*python.*$\n?", "", head, flags=re.M | re.I)
        adjustments.append("Python libraries dropped because this tree does not include Python")
    return head.rstrip(), adjustments


QRC_FILE = re.compile(r"<file(?:\s[^>]*)?>([^<]+)</file>")


def unresolvedResources(manifest: str, files: list[str], text: str) -> list[str]:
    """Entries of a Qt resource manifest that do not exist in the tree (case-insensitively).

    A manifest with missing entries cannot have been compiled by the original project,
    so an inferred project leaves it out (for example the stale ``res/scripts.qrc`` once
    scripts moved to a top-level ``scripts/`` directory loaded from disk).
    """
    present = {path.lower() for path in files}
    base = Path(manifest).parent
    missing_entries = []
    for entry in QRC_FILE.findall(text):
        name = os.path.normpath((base / entry.strip().replace("\\", "/")).as_posix()).replace(os.sep, "/")
        if name.lower() not in present and not any(path.startswith(name.lower() + "/") for path in present):
            missing_entries.append(entry.strip())
    return missing_entries


def project(ref: str) -> str:
    """Write a qmake project from the tree's surviving object_script listing and the nearest intact project."""
    commit = resolve(ref)
    source = WORK / "src" / commit[:8]
    lost = [entry["path"] for entry in missing(commit) if entry["path"].endswith(".pro")]
    if not lost:
        raise SystemExit("this tree's qmake project survived")
    name = lost[0]
    scripts = sorted(source.glob("object_script.*.Debug")) or sorted(source.glob("object_script.*.Release"))
    files = [path.relative_to(source).as_posix() for path in source.rglob("*") if path.is_file()]
    candidates = projectTemplates(commit, name)
    if not candidates:
        raise SystemExit("no intact or reconstructed qmake project survives to supply settings")
    if scripts:
        candidates = [candidate for candidate in candidates if candidate[3] == "intact"] or candidates
    donor, template, _, kind = max(candidates, key=lambda c: (len(templateUnits(c[1], files)), -c[2], c[3] == "intact"))
    sources, unknown = [], []
    if scripts:
        objects = [
            Path(line.strip().replace("\\", "/")).stem
            for line in scripts[0].read_text(errors="replace").splitlines()
            if line.strip().endswith(".o")
        ]
        by_stem: dict[str, list[str]] = {}
        for path in files:
            if path.endswith((".cpp", ".c", ".cc")):
                by_stem.setdefault(Path(path).stem, []).append(path)
        for stem in objects:
            if stem.startswith(("moc_", "qrc_")):
                continue
            matches = by_stem.get(stem, [])
            (sources.append(matches[0]) if len(matches) == 1 else unknown.append(stem))
        origin = f"{len(sources)} sources from {scripts[0].name}"
    else:
        def readTreeFile(path: str) -> str | None:
            try:
                return (source / path).read_text(errors="replace")
            except OSError:
                return None

        sources = donorSources(template, files, readTreeFile)
        origin = (
            f"{len(sources)} sources inferred without a surviving object_script listing: {kind} "
            f"{donor[:8]}:{name} SOURCES reconciled with this tree's files"
        )
    headers = sorted(path for path in files if path.endswith(".h") and not path.startswith("tmp/"))
    head = template.split("SOURCES", 1)[0].rstrip()
    if not scripts and kind == "reconstructed":

        def readTree(path: str) -> str | None:
            try:
                return (source / path).read_text(errors="replace")
            except OSError:
                return None

        head, adjustments = adaptSettings(head, files, readTree)
        if adjustments:
            origin += "; " + "; ".join(adjustments)
    lines = [
        head,
        "",
        "SOURCES += " + " \\\n    ".join(sources),
        "",
        "HEADERS  += \\\n    " + " \\\n    ".join(headers),
        "",
    ]
    resources = sorted(
        path for path in files if path.endswith(".qrc") and not unresolvedResources(path, files, (source / path).read_text(errors="replace"))
    )
    stale = sorted(path for path in files if path.endswith(".qrc") and path not in resources)
    if stale:
        print("left out resource manifests listing files absent from this tree:", stale)
    if resources:
        lines += ["RESOURCES += \\\n    " + " \\\n    ".join(resources), ""]
    forms = sorted(path for path in files if path.endswith(".ui") and not path.startswith("tmp/"))
    if forms:
        lines += ["FORMS += \\\n    " + " \\\n    ".join(forms), ""]
    (source / name).write_text("\n".join(lines))
    summary = f"{origin}; settings from {kind} {donor[:8]}:{name}"
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
        f"--overrides {overrides} --output-dir {output} --timeout {VERIFY_TIMEOUT} --jobs {os.cpu_count() or 1} {extra} > /dev/null; "
        f"/opt/recovery/controller/bin/python3.12 -c 'import json,sys; "
        f'r=json.load(open(sys.argv[1]))["results"][-1]; print(r["status"], r.get("reason",""))\' '
        f"{output}/summary-0.json",
        REPO,
    )
    print(result.stdout.strip() or result.stderr[-2000:])
    return result.stdout.split(" ", 1)[0]


def auto(start: int, end: int, check: bool = False) -> None:
    for number in range(start, end + 1):
        commit = ORDER[number - 1]
        print(f"=== #{number} {commit[:8]}", flush=True)
        prep(str(number), quiet=True)
        carried = carry(str(number))
        generated = [
            (entry["path"], entry["originalBlob"], project(str(number)))
            for entry in missing(commit)
            if entry["path"].endswith(".pro") and not reconstructed(entry["originalBlob"])
        ]
        if not build(str(number), lines=25):
            print(f"STOP at #{number}")
            return
        for path, blob, donor in carried:
            (RECON / blob).write_bytes((WORK / "src" / commit[:8] / path).read_bytes())
            note(blob, f"carried forward unchanged from the {donor} (previous version of {path})")
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
                "legacy_tiles.json",
                "maps_manifest.qrc",
                "teleporter_serialization.cpp",
                "pathfindercache.cpp",
            ):
                if (report_path.parent / name).exists():
                    shutil.copyfile(report_path.parent / name, target / name)
            with gzip.GzipFile(target / "build.log.gz", "wb", mtime=0) as stream:
                stream.write((report_path.parent / "build.log").read_bytes())
            print("exported", commit[:8])


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
            requires_replay = (
                commit in (vh.source_prep.cache_prep.COMMIT, vh.source_prep.console_prep.COMMIT)
                or commit in vh.runtime_configs.INPUT_PINS
                or commit in vh.source_prep.scene_prep.PINS
                or commit == vh.source_prep.panel_prep.COMMIT
                or commit == vh.source_prep.text_shutdown_prep.COMMIT
                or commit == vh.source_prep.sparse_prep.COMMIT
                or commit == vh.source_prep.named_event_prep.COMMIT
                or commit in vh.source_prep.effect_prep.COMMITS
                or commit in vh.source_prep.resources_prep.COMMITS
                or commit in vh.source_prep.import_hook_prep.COMMITS
                or commit in vh.source_prep.map_events_prep.COMMITS
                or commit in vh.source_prep.python_effects_prep.COMMITS
                or commit in vh.source_prep.class_loaders_prep.COMMITS
                or commit in vh.source_prep.map_packages_prep.COMMITS
                or commit in vh.source_prep.potion_movement_prep.COMMITS
                or commit in vh.source_prep.fight_system_prep.COMMITS
                or commit in vh.source_prep.creature_events_prep.COMMITS
                or commit in vh.source_prep.visitor_callbacks_prep.COMMITS
                or commit in vh.source_prep.loader_prep.COMMITS
                or commit in vh.source_prep.panel_refresh_prep.PROFILES
                or commit in vh.source_prep.shutdown_prep.TARGETS
                or commit in (vh.source_prep.trigger_prep.COMMIT, vh.source_prep.position_prep.COMMIT)
            )
            if requires_replay or commit in vh.source_prep.merged_prep.COMMITS or report.get("startupCompatibility") in (
                "parentReflectionRegistration",
                "originalCoordinateHash",
                "legacyTileConfiguration",
                "authoredMapsManifest",
                "teleporterSerialization",
                "legacyTimingResources",
            ):
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
            if report.get("startupCompatibility") == "legacyTileConfiguration":
                item["startupCompatibility"] = "legacyTileConfiguration"
                item["validation"] = "build-and-startup-with-legacy-tile-compatibility-passed"
            if report.get("startupCompatibility") == "authoredMapsManifest":
                item["startupCompatibility"] = "authoredMapsManifest"
                item["validation"] = "build-and-startup-with-maps-manifest-compatibility-passed"
            if report.get("startupCompatibility") == "teleporterSerialization":
                item["startupCompatibility"] = "teleporterSerialization"
                item["validation"] = "build-and-startup-with-teleporter-serialization-compatibility-passed"
            if report.get("startupCompatibility") == "legacyTimingResources":
                item["startupCompatibility"] = "legacyTimingResources"
                item["validation"] = "build-and-startup-with-legacy-timing-resource-compatibility-passed"
            if commit in vh.source_prep.scene_prep.PINS:
                item["buildCompatibility"] = ["sceneTransition"]
            if commit in vh.source_prep.shutdown_prep.TARGETS:
                item["buildCompatibility"] = ["pythonShutdown"]
            if commit == vh.source_prep.panel_prep.COMMIT:
                item["buildCompatibility"] = ["panelTransition"]
            if commit == vh.source_prep.text_shutdown_prep.COMMIT:
                item["buildCompatibility"] = ["textPanelShutdown"]
            if commit == vh.source_prep.sparse_prep.COMMIT:
                item["buildCompatibility"] = ["sparseMapTransition"]
            if commit == vh.source_prep.named_event_prep.COMMIT:
                item["buildCompatibility"] = ["namedEventTransition"]
            if commit in vh.source_prep.resources_prep.COMMITS:
                item["buildCompatibility"] = ["resourcesTransition"]
            if commit in vh.source_prep.import_hook_prep.COMMITS:
                item["buildCompatibility"] = ["importHook"]
            if commit in vh.source_prep.map_events_prep.COMMITS:
                item["buildCompatibility"] = ["mapEvents"]
            if commit in vh.source_prep.python_effects_prep.COMMITS:
                item["buildCompatibility"] = ["pythonEffects"]
            if commit in vh.source_prep.class_loaders_prep.COMMITS:
                item["buildCompatibility"] = ["classLoaders"]
            if commit in vh.source_prep.map_packages_prep.COMMITS:
                item["buildCompatibility"] = ["mapPackages"]
            if commit in vh.source_prep.potion_movement_prep.COMMITS:
                item["buildCompatibility"] = ["potionMovement"]
            if commit in vh.source_prep.fight_system_prep.COMMITS:
                item["buildCompatibility"] = ["fightSystem"]
            if commit in vh.source_prep.creature_events_prep.COMMITS:
                item["buildCompatibility"] = ["creatureEvents"]
            if commit in vh.source_prep.visitor_callbacks_prep.COMMITS:
                item["buildCompatibility"] = ["visitorCallbacks"]
            if commit in vh.source_prep.loader_prep.COMMITS:
                item["buildCompatibility"] = ["scriptLoader"]
            if commit in vh.source_prep.effect_prep.COMMITS:
                item["buildCompatibility"] = ["effectTransition"]
            if commit in vh.source_prep.panel_refresh_prep.PROFILES:
                item["buildCompatibility"] = ["panelRefreshTransition"]
            if commit == vh.source_prep.position_prep.COMMIT:
                item["buildCompatibility"] = ["mapPosition"]
            if commit == vh.source_prep.trigger_prep.COMMIT:
                item["buildCompatibility"] = ["triggerDecorator"]
            if commit == vh.source_prep.console_prep.COMMIT:
                item["buildCompatibility"] = ["consoleReader"]
            if commit in vh.source_prep.merged_prep.COMMITS:
                item["buildCompatibility"] = ["mergedHeaders"]
            if commit == vh.source_prep.cache_prep.COMMIT:
                item["buildCompatibility"] = ["trivialConflicts", "childPathfinderCache"]
            if commit in vh.runtime_configs.INPUT_PINS:
                item["startupCompatibility"] = "transitionalRuntimeConfiguration"
                item["validation"] = "build-and-startup-with-runtime-configuration-compatibility-passed"
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
    else:
        export()


if __name__ == "__main__":
    main()
