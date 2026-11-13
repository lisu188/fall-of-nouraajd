#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Inventory BFG markers and materialize a separate, provenance-bearing recovery history."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile

MARKER_SUFFIX = ".REMOVED.git-id"
OBJECT_ID = re.compile(r"[0-9a-f]{40}\Z")
GENERATED_SUFFIXES = {
    ".apk",
    ".dll",
    ".exe",
    ".lib",
    ".o",
    ".obj",
    ".pyc",
    ".pyo",
    ".zip",
    ".7z",
    ".a",
    ".so",
}


class RecoveryError(ValueError):
    pass


def gitCommand(repo_root, *args, data=None, env=None):
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args], input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
    )
    if result.returncode:
        raise RecoveryError(result.stderr.decode("utf-8", "replace").strip() or f"git {args[0]} failed")
    return result.stdout


def objectHash(kind, content):
    return hashlib.sha1(kind.encode() + b" " + str(len(content)).encode() + b"\0" + content).hexdigest()


def safePath(value):
    if not isinstance(value, str):
        raise RecoveryError(f"Unsafe repository path: {value!r}")
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or "\0" in value
        or path.is_absolute()
        or path.as_posix() != value
        or any(part in (".", "..") or part.lower() == ".git" for part in path.parts)
    ):
        raise RecoveryError(f"Unsafe repository path: {value!r}")
    return value


def exclusionReason(path):
    name = PurePosixPath(path).name
    if PurePosixPath(path).suffix.lower() in GENERATED_SUFFIXES:
        return "generated binary, redistributable, or packaged artifact"
    if name.startswith("Makefile") or name.startswith("moc_") or name.startswith("qrc_"):
        return "generated build output"
    if ".user" in name or name in (".cproject", ".project", ".DS_Store"):
        return "machine-specific IDE state"
    return None


class GitObjects:
    def __init__(self, repo_root):
        self.repo_root = Path(repo_root).resolve()
        if gitCommand(self.repo_root, "rev-parse", "--show-object-format").strip() != b"sha1":
            raise RecoveryError("BFG SHA-1 recovery requires a SHA-1 Git repository")
        self.process = subprocess.Popen(
            ["git", "-C", str(self.repo_root), "cat-file", "--batch"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.cache = {}
        self.marker_cache = {}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.process.stdin.close()
        self.process.stdout.close()
        self.process.stderr.close()
        self.process.wait()

    def read(self, oid, expected=None, missing_ok=False):
        if not OBJECT_ID.fullmatch(oid):
            raise RecoveryError(f"Invalid Git object id: {oid!r}")
        if oid not in self.cache:
            self.process.stdin.write((oid + "\n").encode())
            self.process.stdin.flush()
            header = self.process.stdout.readline().decode().split()
            if len(header) == 2 and header[1] == "missing":
                self.cache[oid] = None
            elif len(header) == 3:
                size = int(header[2])
                content = self.process.stdout.read(size)
                if len(content) != size or self.process.stdout.read(1) != b"\n":
                    raise RecoveryError(f"Truncated Git object: {oid}")
                if objectHash(header[1], content) != oid:
                    raise RecoveryError(f"Git object hash mismatch: {oid}")
                self.cache[oid] = (header[1], content)
            else:
                raise RecoveryError(f"Unexpected git cat-file response: {header!r}")
        result = self.cache[oid]
        if result is None:
            if missing_ok:
                return None
            raise RecoveryError(f"Missing Git object: {oid}")
        if expected is not None and result[0] != expected:
            raise RecoveryError(f"Expected {expected}, found {result[0]}: {oid}")
        return result[1]

    def tree(self, oid):
        content = self.read(oid, "tree")
        position = 0
        while position < len(content):
            end = content.index(b"\0", position)
            mode, name = content[position:end].split(b" ", 1)
            child = content[end + 1 : end + 21].hex()
            yield mode.decode(), name.decode("utf-8", "surrogateescape"), child
            position = end + 21

    def markers(self, tree):
        if tree not in self.marker_cache:
            entries = []
            for mode, name, oid in self.tree(tree):
                if mode == "40000":
                    entries.extend(
                        {**item, "markerPath": name + "/" + item["markerPath"]} for item in self.markers(oid)
                    )
                elif name.endswith(MARKER_SUFFIX):
                    entries.append({"markerPath": name, "markerBlob": oid, "mode": mode})
            self.marker_cache[tree] = entries
        return self.marker_cache[tree]

    def files(self, tree, prefix=""):
        result = {}
        for mode, name, oid in self.tree(tree):
            path = safePath(prefix + name)
            if mode == "40000":
                result.update(self.files(oid, path + "/"))
            else:
                result[path] = {"mode": mode, "blob": oid}
        return result


def readJson(path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def writeJson(path, value):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def auditHistory(repo_root, original_manifest=None):
    if original_manifest is not None:
        original_refs = dict(original_manifest["originalRefs"])
    else:
        original_refs = {}
        lines = gitCommand(repo_root, "for-each-ref", "--format=%(refname) %(objectname)").decode().splitlines()
        for line in lines:
            ref, oid = line.split()
            if ref.startswith("refs/original/") or ref.startswith("refs/replace/"):
                continue
            if re.search(r"(?:^|/)recovery/", ref):
                continue
            try:
                gitCommand(repo_root, "rev-parse", "--verify", oid + "^{commit}")
            except RecoveryError:
                continue
            original_refs[ref] = oid
    if not original_refs:
        raise RecoveryError("No original commit refs found")
    for oid in original_refs.values():
        if not OBJECT_ID.fullmatch(oid):
            raise RecoveryError("Original manifest contains an invalid object id")
    history = (
        gitCommand(
            repo_root,
            "rev-list",
            "--reverse",
            "--topo-order",
            "--parents",
            "--stdin",
            data=("\n".join(sorted(set(original_refs.values()))) + "\n").encode(),
        )
        .decode()
        .splitlines()
    )
    commits, trees = [], {}
    with GitObjects(repo_root) as objects:
        for line in history:
            commit, *parents = line.split()
            content = objects.read(commit, "commit")
            tree = content.split(b"\n", 1)[0].decode().removeprefix("tree ")
            markers = objects.markers(tree)
            commits.append({"commit": commit, "tree": tree, "parents": parents, "damaged": bool(markers)})
            if markers:
                if tree not in trees:
                    entries = []
                    for marker in markers:
                        path = safePath(marker["markerPath"][: -len(MARKER_SUFFIX)])
                        raw = objects.read(marker["markerBlob"], "blob")
                        target = raw.strip().decode("ascii", "replace")
                        reason = exclusionReason(path)
                        entry = {**marker, "path": path, "originalBlob": target}
                        if not OBJECT_ID.fullmatch(target):
                            entry["status"] = "malformed"
                        elif reason:
                            entry.update(status="excludedGenerated", reason=reason)
                        elif objects.read(target, "blob", missing_ok=True) is not None:
                            entry["status"] = "exactAvailable"
                        else:
                            entry["status"] = "missingOriginal"
                        entries.append(entry)
                    trees[tree] = {
                        "tree": tree,
                        "commits": [],
                        "entries": sorted(entries, key=lambda item: item["path"]),
                    }
                trees[tree]["commits"].append(commit)
    damaged_ids = {item["commit"] for item in commits if item["damaged"]}
    damaged_ancestors = set()
    for item in reversed(commits):
        if item["damaged"] or item["commit"] in damaged_ancestors:
            damaged_ancestors.update(item["parents"])
    versions = {item["markerBlob"]: item for tree in trees.values() for item in tree["entries"]}
    return {
        "schemaVersion": 1,
        "originalRefs": dict(sorted(original_refs.items())),
        "commits": commits,
        "trees": sorted(trees.values(), key=lambda item: item["tree"]),
        "damagedTips": sorted(damaged_ids - damaged_ancestors),
        "summary": {
            "commitCount": len(commits),
            "damagedCommitCount": len(damaged_ids),
            "damagedTreeCount": len(trees),
            "pointerVersionCount": len(versions),
            "uniquePointerPaths": len({entry["path"] for tree in trees.values() for entry in tree["entries"]}),
            "exactOriginalCount": sum(item["status"] == "exactAvailable" for item in versions.values()),
            "missingOriginalCount": sum(item["status"] == "missingOriginal" for item in versions.values()),
            "excludedVersionCount": sum(item["status"] == "excludedGenerated" for item in versions.values()),
            "malformedVersionCount": sum(item["status"] == "malformed" for item in versions.values()),
        },
    }


def loadOverrides(path):
    if path is None:
        return {"schemaVersion": 1, "entries": []}
    result = readJson(path)
    result["_baseDir"] = str(Path(path).resolve().parent)
    return result


def selectedOverrides(overrides, commit, tree):
    selected = {}
    priorities = {}
    seen = set()
    for entry in (overrides or {}).get("entries", []):
        path = safePath(entry["path"])
        if entry.get("commit") not in (None, commit) or entry.get("tree") not in (None, tree):
            continue
        priority = 2 if entry.get("commit") else 1 if entry.get("tree") else 0
        if (path, priority) in seen:
            raise RecoveryError(f"Duplicate recovery override: {path}")
        seen.add((path, priority))
        if priority > priorities.get(path, -1):
            selected[path] = entry
            priorities[path] = priority
    return selected


def overrideContent(objects, overrides, entry):
    if not entry.get("provenance"):
        raise RecoveryError(f"Recovery override lacks provenance: {entry['path']}")
    if "blob" in entry and "source" not in entry:
        return objects.read(entry["blob"], "blob")
    if "source" not in entry or "blob" in entry:
        raise RecoveryError(f"Recovery override needs exactly one source or blob: {entry['path']}")
    source = safePath(entry["source"])
    base = Path(overrides.get("_baseDir", ".")).resolve()
    target = (base / source).resolve()
    if not target.is_relative_to(base):
        raise RecoveryError(f"Recovery payload escapes its catalog directory: {source}")
    content = target.read_bytes()
    if hashlib.sha256(content).hexdigest() != entry.get("sha256"):
        raise RecoveryError(f"Recovery payload SHA-256 mismatch: {source}")
    return content


def prepareSnapshot(objects, catalog, commit, overrides=None, allow_incomplete=False):
    metadata = next((item for item in catalog["commits"] if item["commit"] == commit), None)
    if metadata is None:
        raise RecoveryError(f"Commit absent from original catalog: {commit}")
    tree = metadata["tree"]
    actual_tree = objects.read(commit, "commit").split(b"\n", 1)[0].decode().removeprefix("tree ")
    if actual_tree != tree:
        raise RecoveryError(f"Catalog tree does not match original commit: {commit}")
    files = objects.files(tree)
    chosen = selectedOverrides(overrides, commit, tree)
    restored, excluded, unresolved = [], [], []
    markers = sorted(path for path in files if path.endswith(MARKER_SUFFIX))
    for marker_path in markers:
        marker = files.pop(marker_path)
        path = safePath(marker_path[: -len(MARKER_SUFFIX)])
        target = objects.read(marker["blob"], "blob").strip().decode("ascii", "replace")
        record = {"path": path, "markerPath": marker_path, "originalBlob": target}
        if not OBJECT_ID.fullmatch(target):
            unresolved.append({**record, "reason": "malformed BFG pointer"})
            continue
        if path in files and not chosen.get(path, {}).get("replaceExisting"):
            restored.append({**record, "method": "existingFile", "replacementBlob": files[path]["blob"]})
            chosen.pop(path, None)
            continue
        reason = exclusionReason(path)
        if reason:
            excluded.append({**record, "reason": reason})
            chosen.pop(path, None)
            continue
        exact = objects.read(target, "blob", missing_ok=True)
        if exact is not None:
            files[path] = {"mode": marker["mode"], "blob": target}
            restored.append({**record, "method": "exactOriginal", "replacementBlob": target})
            if not chosen.get(path, {}).get("replaceExisting"):
                chosen.pop(path, None)
        elif path in chosen:
            entry = chosen.pop(path)
            content = overrideContent(objects, overrides, entry)
            files[path] = {"mode": entry.get("mode", marker["mode"]), "content": content}
            restored.append(
                {
                    **record,
                    "method": "reconstruction",
                    "replacementBlob": objectHash("blob", content),
                    "provenance": entry["provenance"],
                }
            )
        else:
            unresolved.append({**record, "reason": "original blob missing and no reconstruction supplied"})
    for path, entry in sorted(chosen.items()):
        if path in files and not entry.get("replaceExisting"):
            raise RecoveryError(f"Overriding an existing file requires replaceExisting: {path}")
        if path not in files and not entry.get("add"):
            raise RecoveryError(f"Adding a file requires add: {path}")
        content = overrideContent(objects, overrides, entry)
        files[path] = {"mode": entry.get("mode", files.get(path, {}).get("mode", "100644")), "content": content}
        restored.append(
            {
                "path": path,
                "method": "compatibilityRepair",
                "replacementBlob": objectHash("blob", content),
                "provenance": entry["provenance"],
            }
        )
    if unresolved and not allow_incomplete:
        paths = ", ".join(item["path"] for item in unresolved[:8])
        raise RecoveryError(f"{len(unresolved)} unresolved required files in {commit}: {paths}")
    for path, entry in files.items():
        if entry["mode"] not in ("100644", "100755", "120000", "160000"):
            raise RecoveryError(f"Unsupported file mode {entry['mode']}: {path}")
        for parent in PurePosixPath(path).parents:
            if parent.as_posix() in files:
                raise RecoveryError(f"Recovery file/directory collision: {path}")
    return files, {
        "sourceCommit": commit,
        "sourceTree": tree,
        "status": "incomplete" if unresolved else "complete",
        "restored": restored,
        "excluded": excluded,
        "unresolved": unresolved,
    }


def validateReplayCatalog(objects, catalog):
    if catalog.get("schemaVersion") != 1:
        raise RecoveryError("Unsupported recovery catalog schema")
    seen, damaged, ancestors = set(), set(), set()
    for item in catalog["commits"]:
        commit = item["commit"]
        content = objects.read(commit, "commit").split(b"\n\n", 1)[0].split(b"\n")
        tree = content[0].decode().removeprefix("tree ")
        parents = [line[7:].decode() for line in content if line.startswith(b"parent ")]
        if commit in seen or not set(parents).issubset(seen):
            raise RecoveryError("Catalog commits must be unique and ordered before their children")
        if tree != item["tree"] or parents != item["parents"] or bool(objects.markers(tree)) != item["damaged"]:
            raise RecoveryError(f"Catalog metadata does not match original commit: {commit}")
        if item["damaged"]:
            damaged.add(commit)
        seen.add(commit)
    for item in reversed(catalog["commits"]):
        if item["damaged"] or item["commit"] in ancestors:
            ancestors.update(item["parents"])
    if sorted(damaged - ancestors) != catalog["damagedTips"]:
        raise RecoveryError("Catalog damaged tips do not cover the damaged history")
    original_ids = sorted(set(catalog["originalRefs"].values()))
    if not original_ids or any(not OBJECT_ID.fullmatch(oid) for oid in original_ids):
        raise RecoveryError("Catalog original refs are missing or invalid")
    reachable = gitCommand(objects.repo_root, "rev-list", "--stdin", data=("\n".join(original_ids) + "\n").encode())
    if set(reachable.decode().splitlines()) != seen:
        raise RecoveryError("Catalog does not cover every commit reachable from its frozen original refs")


def restoreSnapshot(repo_root, catalog, commit, output_dir, overrides=None, allow_incomplete=False):
    output = Path(output_dir).absolute()
    if output.exists() or output.is_symlink():
        raise RecoveryError(f"Output directory must be new: {output}")
    with GitObjects(repo_root) as objects:
        files, report = prepareSnapshot(objects, catalog, commit, overrides, allow_incomplete)
        payloads = {}
        for path, entry in files.items():
            if entry["mode"] == "160000":
                continue
            content = entry.get("content")
            if content is None:
                content = objects.read(entry["blob"], "blob")
            if entry["mode"] == "120000":
                link = content.decode("utf-8", "surrogateescape")
                if (
                    "\0" in link
                    or "\\" in link
                    or not (output / path).parent.joinpath(link).resolve().is_relative_to(output)
                ):
                    raise RecoveryError(f"Symlink escapes recovered snapshot: {path}")
            payloads[path] = content
        output.mkdir(parents=True)
        for path, entry in sorted(files.items(), key=lambda item: (item[1]["mode"] == "120000", item[0])):
            target = output / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if entry["mode"] == "160000":
                target.mkdir()
            elif entry["mode"] == "120000":
                target.symlink_to(payloads[path].decode("utf-8", "surrogateescape"))
            else:
                target.write_bytes(payloads[path])
                target.chmod(0o755 if entry["mode"] == "100755" else 0o644)
    return {
        **report,
        "outputDir": str(output),
        "submodules": [
            {"path": path, "commit": entry["blob"]}
            for path, entry in sorted(files.items())
            if entry["mode"] == "160000"
        ],
    }


def writeTree(repo_root, files):
    directories = {}
    for path, entry in sorted(files.items()):
        parts = PurePosixPath(path).parts
        cursor = directories
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        oid = entry.get("blob")
        if "content" in entry:
            oid = gitCommand(repo_root, "hash-object", "-w", "--stdin", data=entry["content"]).decode().strip()
        cursor[parts[-1]] = (entry["mode"], oid)

    def writeDirectory(directory):
        entries = []
        for name, value in sorted(directory.items()):
            if isinstance(value, dict):
                mode, kind, oid = "040000", "tree", writeDirectory(value)
            else:
                mode, oid = value
                kind = "commit" if mode == "160000" else "blob"
            entries.append(f"{mode} {kind} {oid}\t".encode() + name.encode("utf-8", "surrogateescape") + b"\0")
        return gitCommand(repo_root, "mktree", "-z", "--missing", data=b"".join(entries)).decode().strip()

    return writeDirectory(directories)


def replayHistory(repo_root, catalog, overrides=None):
    # Resolve every required reconstruction before writing any recovery object.
    prepared = {}
    with GitObjects(repo_root) as objects:
        validateReplayCatalog(objects, catalog)
        metadata = {item["commit"]: item for item in catalog["commits"]}
        required, pending = set(), list(catalog["damagedTips"])
        while pending:
            commit = pending.pop()
            if commit not in required:
                required.add(commit)
                pending.extend(metadata[commit]["parents"])
        for item in catalog["commits"]:
            if item["commit"] in required and item["damaged"]:
                prepared[item["commit"]] = prepareSnapshot(objects, catalog, item["commit"], overrides)
        mapping, reports = {}, []
        for item in catalog["commits"]:
            commit = item["commit"]
            if commit not in required:
                continue
            parents = [mapping[parent] for parent in item["parents"]]
            if commit not in prepared and parents == item["parents"]:
                mapping[commit] = commit
                continue
            if commit in prepared:
                files, report = prepared[commit]
                tree = writeTree(repo_root, files)
                reports.append(report)
            else:
                tree = item["tree"]
            content = objects.read(commit, "commit")
            headers, message = content.split(b"\n\n", 1)
            identity = [
                line for line in headers.split(b"\n") if line.startswith((b"author ", b"committer ", b"encoding "))
            ]
            replacement = b"tree " + tree.encode() + b"\n"
            replacement += b"".join(b"parent " + parent.encode() + b"\n" for parent in parents)
            replacement += b"\n".join(identity) + b"\n\n" + message.rstrip(b"\n")
            replacement += b"\n\nRecovered-from-commit: " + commit.encode() + b"\n"
            mapping[commit] = (
                gitCommand(repo_root, "hash-object", "-t", "commit", "-w", "--stdin", data=replacement).decode().strip()
            )
    refs = {"refs/heads/recovery/bfg/" + tip: mapping[tip] for tip in catalog["damagedTips"]}
    return {
        "schemaVersion": 1,
        "status": "complete",
        "originalRefs": catalog["originalRefs"],
        "commitMap": dict(sorted(mapping.items())),
        "recoveryRefs": refs,
        "reports": reports,
    }


def bundleHistory(repo_root, mapping, output):
    target = Path(output).absolute()
    if target.exists():
        raise RecoveryError(f"Bundle output must be new: {target}")
    if mapping.get("status") != "complete" or not mapping.get("recoveryRefs"):
        raise RecoveryError("Bundle requires a complete replay mapping with recovery refs")
    object_dir = Path(gitCommand(repo_root, "rev-parse", "--git-path", "objects").decode().strip())
    if not object_dir.is_absolute():
        object_dir = Path(repo_root).resolve() / object_dir
    with tempfile.TemporaryDirectory(prefix="nouraajd-recovery-bundle-") as temporary:
        bare = Path(temporary) / "bundle.git"
        subprocess.run(["git", "init", "--bare", "--quiet", "--initial-branch=main", str(bare)], check=True)
        (bare / "objects" / "info" / "alternates").write_text(str(object_dir.resolve()) + "\n", encoding="utf-8")
        for ref, oid in sorted(mapping["recoveryRefs"].items()):
            if not ref.startswith("refs/heads/recovery/bfg/") or not OBJECT_ID.fullmatch(oid):
                raise RecoveryError("Invalid recovery bundle ref")
            gitCommand(bare, "check-ref-format", ref)
            gitCommand(bare, "update-ref", ref, oid)
        target.parent.mkdir(parents=True, exist_ok=True)
        gitCommand(bare, "bundle", "create", str(target), "--all")
        verification = gitCommand(bare, "bundle", "verify", str(target)).decode().strip()
    with target.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {
        "status": "verified",
        "bundle": str(target),
        "sha256": digest,
        "recoveryRefs": mapping["recoveryRefs"],
        "verification": verification,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("audit", "restore", "replay", "bundle"):
        child = subparsers.add_parser(command)
        child.add_argument("--repo-root", type=Path, default=Path("."))
        if command != "bundle":
            child.add_argument("--catalog", type=Path, required=True)
        if command == "audit":
            child.add_argument("--original-manifest", type=Path)
        if command in ("restore", "replay"):
            child.add_argument("--overrides", type=Path)
        if command == "restore":
            child.add_argument("--commit", required=True)
            child.add_argument("--output-dir", type=Path, required=True)
            child.add_argument("--allow-incomplete", action="store_true")
            child.add_argument("--report", type=Path)
        if command in ("replay", "bundle"):
            child.add_argument("--output", type=Path, required=True)
        if command == "bundle":
            child.add_argument("--mapping", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "audit":
            frozen = args.original_manifest or (args.catalog if args.catalog.exists() else None)
            result = auditHistory(args.repo_root, readJson(frozen) if frozen else None)
            writeJson(args.catalog, result)
            result = result["summary"]
        elif args.command == "restore":
            result = restoreSnapshot(
                args.repo_root,
                readJson(args.catalog),
                args.commit,
                args.output_dir,
                loadOverrides(args.overrides),
                args.allow_incomplete,
            )
            if args.report:
                writeJson(args.report, result)
        elif args.command == "replay":
            result = replayHistory(args.repo_root, readJson(args.catalog), loadOverrides(args.overrides))
            writeJson(args.output, result)
            result = {
                "status": result["status"],
                "mappedCommits": len(result["commitMap"]),
                "recoveryRefs": result["recoveryRefs"],
            }
        else:
            result = bundleHistory(args.repo_root, readJson(args.mapping), args.output)
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (RecoveryError, OSError, KeyError, TypeError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"Recovery blocked: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
