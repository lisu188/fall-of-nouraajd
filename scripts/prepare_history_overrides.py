#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Propose reproducible historical donors without claiming that reconstructed snapshots compile."""

import argparse
from collections import defaultdict, deque
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct
import sys
import zlib

try:
    from scripts import recover_history as recovery
except ModuleNotFoundError:
    import recover_history as recovery


DEFAULT_DONORS = ("55e6516e", "108bdcbe", "8965c542")
EARLIEST_ORIGINAL = "b9ae428b"
EARLIEST_DONOR = "108bdcbe"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
SOURCE_EXTENSIONS = {".cpp", ".cc", ".c", ".h", ".hpp", ".inl"}
IGNORE_METHODS = {"if", "for", "while", "switch", "return", "sizeof", "static_cast", "dynamic_cast"}


def canonicalName(path):
    name = PurePosixPath(path).name
    return re.sub(r"^C(?=[A-Z])", "", name).lower().replace("iteraction.", "interaction.")


def isImage(path):
    return PurePosixPath(path).suffix.lower() in IMAGE_EXTENSIONS or (
        path.startswith("images/") and not PurePosixPath(path).suffix
    )


def assetName(path):
    normalized = path.lower()
    for prefix in ("res/", "files/", "assets/"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
    normalized = re.sub(r"/0\.(png|jpe?g)$", r".\1", normalized)
    normalized = re.sub(r"/0$", "", normalized)
    return re.sub(r"\.(png|jpe?g)$", "", normalized)


def imagePlaceholder(path):
    """An intentionally conspicuous replacement, never represented as original artwork."""
    digest = hashlib.sha256(path.encode("utf-8")).digest()
    color = tuple(48 + channel % 160 for channel in digest[:3])
    rows = []
    for y in range(32):
        row = bytearray([0])
        for x in range(32):
            pixel = (255, 0, 255) if (x // 4 + y // 4) % 2 else color
            row.extend((*pixel, 255))
        rows.append(bytes(row))

    def chunk(kind, content):
        return struct.pack("!I", len(content)) + kind + content + struct.pack("!I", zlib.crc32(kind + content))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack("!IIBBBBB", 32, 32, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
        + chunk(b"IEND", b"")
    )


def apiShape(content):
    text = content.decode("utf-8", "replace")
    text = re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.DOTALL)
    classes = set(re.findall(r"\b(?:class|struct)\s+([A-Za-z_]\w*)", text))
    classes.update(re.findall(r"\b([A-Za-z_]\w*)::[~A-Za-z_]\w*\s*\(", text))
    methods = set(re.findall(r"\b([~A-Za-z_]\w*)\s*\(", text)) - IGNORE_METHODS
    return classes, methods


def companionHeader(files, path):
    source = PurePosixPath(path)
    if source.stem == "CIteraction":
        source = source.with_name("CInteraction.cpp")
    for suffix in (".h", ".hpp"):
        candidate = source.with_suffix(suffix).as_posix()
        if candidate != path and candidate in files:
            entry = files[candidate]
            if entry["mode"] in ("100644", "100755"):
                return entry["blob"]
    return None


def graphDistances(graph, starts):
    distances = {commit: 0 for commit in starts}
    queue = deque(starts)
    while queue:
        commit = queue.popleft()
        for neighbor in sorted(graph[commit]):
            if neighbor not in distances:
                distances[neighbor] = distances[commit] + 1
                queue.append(neighbor)
    return distances


def pathSimilarity(first, second):
    left, right = PurePosixPath(first).parts, PurePosixPath(second).parts
    common = 0
    for a, b in zip(reversed(left), reversed(right)):
        if a.lower() != b.lower():
            break
        common += 1
    return common


def donorScore(objects, candidate, target_path, target_header, distances, shape_cache):
    def shape(oid):
        if oid not in shape_cache:
            shape_cache[oid] = apiShape(objects.read(oid, "blob"))
        return shape_cache[oid]

    header_match = int(target_header is not None and target_header == candidate["header"])
    overlap, classes_match = 0, 0
    if target_header is not None:
        target_classes, target_methods = shape(target_header)
        candidate_classes, candidate_methods = shape(candidate["header"] or candidate["blob"])
        classes_match = int(bool(target_classes & candidate_classes))
        union = target_methods | candidate_methods
        overlap = 10000 * len(target_methods & candidate_methods) // max(1, len(union))
    distance, commit = min((distances.get(commit, 10**9), commit) for commit in candidate["commits"])
    return (
        header_match,
        classes_match,
        overlap,
        pathSimilarity(target_path, candidate["path"]),
        -distance,
        candidate["blob"],
        candidate["path"],
        commit,
    )


def upstreamEntries(repo_root):
    upstream_root = Path(repo_root).resolve() / "recovery" / "upstream"
    entries = []
    for catalog_path in sorted(upstream_root.rglob("catalog.json")):
        for entry in recovery.readJson(catalog_path).get("entries", []):
            source = recovery.safePath(entry["source"])
            payload = (catalog_path.parent / source).resolve()
            if not payload.is_relative_to(catalog_path.parent.resolve()):
                raise recovery.RecoveryError(f"Upstream payload escapes catalog: {source}")
            content = payload.read_bytes()
            if hashlib.sha256(content).hexdigest() != entry["sha256"]:
                raise recovery.RecoveryError(f"Upstream payload SHA-256 mismatch: {source}")
            relative = catalog_path.parent.relative_to(upstream_root) / source
            entries.append({**entry, "source": "upstream/" + relative.as_posix(), "_content": content})
    return entries


def upstreamForTree(entries, tree):
    selected = {}
    for entry in entries:
        if entry.get("tree") not in (None, tree):
            continue
        path = recovery.safePath(entry["path"])
        previous = selected.get(path)
        if previous is not None and bool(previous.get("tree")) == bool(entry.get("tree")):
            raise recovery.RecoveryError(f"Duplicate upstream reconstruction: {tree}:{path}")
        if previous is None or entry.get("tree"):
            selected[path] = entry
    return selected


def proposeOverrides(repo_root, catalog, donor_commits=None, earliest_compatibility=True):
    donors = DEFAULT_DONORS if donor_commits is None else donor_commits
    snapshots = {item["tree"]: list(item["commits"]) for item in catalog["trees"]}
    graph = defaultdict(set)
    for item in catalog["commits"]:
        for parent in item["parents"]:
            graph[item["commit"]].add(parent)
            graph[parent].add(item["commit"])
    wanted_names, wanted_assets = set(), set()
    for snapshot in catalog["trees"]:
        for entry in snapshot["entries"]:
            if entry["status"] == "missingOriginal":
                if isImage(entry["path"]):
                    wanted_assets.add(assetName(entry["path"]))
                else:
                    wanted_names.add(canonicalName(entry["path"]))
    candidates = defaultdict(dict)
    files_by_tree, commit_trees = {}, {}
    entries, unresolved, payloads = [], [], {}
    upstream = upstreamEntries(repo_root)
    counts = {
        "donorEntryCount": 0,
        "placeholderEntryCount": 0,
        "compatibilityEntryCount": 0,
        "exactOrExistingCount": 0,
        "upstreamEntryCount": 0,
    }
    with recovery.GitObjects(repo_root) as objects:
        for donor in donors:
            commit = recovery.gitCommand(repo_root, "rev-parse", "--verify", donor + "^{commit}").decode().strip()
            content = objects.read(commit, "commit").split(b"\n\n", 1)[0].split(b"\n")
            tree = content[0].decode().removeprefix("tree ")
            commit_trees[commit] = tree
            snapshots.setdefault(tree, []).append(commit)
            for line in content:
                if line.startswith(b"parent "):
                    parent = line[7:].decode()
                    graph[commit].add(parent)
                    graph[parent].add(commit)
        for tree, commits in sorted(snapshots.items()):
            files = objects.files(tree)
            files_by_tree[tree] = files
            for path, entry in files.items():
                if path.endswith(recovery.MARKER_SUFFIX) or entry["mode"] not in ("100644", "100755"):
                    continue
                image = isImage(path)
                name = assetName(path) if image else canonicalName(path)
                if name not in (wanted_assets if image else wanted_names):
                    continue
                header = (
                    companionHeader(files, path) if PurePosixPath(path).suffix.lower() in SOURCE_EXTENSIONS else None
                )
                key = (path, entry["blob"], header)
                candidate = candidates[(image, name)].setdefault(
                    key,
                    {
                        "path": path,
                        "blob": entry["blob"],
                        "mode": entry["mode"],
                        "header": header,
                        "commits": set(),
                    },
                )
                candidate["commits"].update(commits)
        compatibility = {}
        earliest = next((item for item in catalog["commits"] if item["commit"].startswith(EARLIEST_ORIGINAL)), None)
        earliest_donor = next((commit for commit in commit_trees if commit.startswith(EARLIEST_DONOR)), None)
        if earliest_compatibility and earliest and earliest_donor:
            original_files = files_by_tree[earliest["tree"]]
            donor_files = files_by_tree[commit_trees[earliest_donor]]
            for path, entry in donor_files.items():
                if path.endswith(recovery.MARKER_SUFFIX) or original_files.get(path) == entry:
                    continue
                compatibility[path] = {
                    "tree": earliest["tree"],
                    "path": path,
                    "blob": entry["blob"],
                    "mode": entry["mode"],
                    "provenance": f"unverified donor reconstruction; earliest compatibility set {earliest_donor}:{path}",
                }
                if path in original_files:
                    compatibility[path]["replaceExisting"] = True
                elif path + recovery.MARKER_SUFFIX not in original_files:
                    compatibility[path]["add"] = True
        shape_cache = {}
        for snapshot in catalog["trees"]:
            tree = snapshot["tree"]
            files = files_by_tree[tree]
            distances = graphDistances(graph, snapshot["commits"])
            chosen_upstream = upstreamForTree(upstream, tree)
            applied_upstream = set()
            for entry in snapshot["entries"]:
                path = entry["path"]
                if tree == (earliest or {}).get("tree") and path in compatibility:
                    continue
                if path in files or entry["status"] == "exactAvailable":
                    counts["exactOrExistingCount"] += 1
                    continue
                if entry["status"] == "excludedGenerated":
                    continue
                if entry["status"] != "missingOriginal":
                    unresolved.append({"tree": tree, "path": path, "reason": entry["status"]})
                    continue
                if path in chosen_upstream:
                    replacement = chosen_upstream[path]
                    payloads[replacement["source"]] = replacement["_content"]
                    entries.append(
                        {
                            key: value
                            for key, value in {**replacement, "tree": tree}.items()
                            if key not in ("_content", "whenPrefix")
                        }
                    )
                    counts["upstreamEntryCount"] += 1
                    applied_upstream.add(path)
                    continue
                image = isImage(path)
                name = assetName(path) if image else canonicalName(path)
                options = list(candidates[(image, name)].values())
                if options:
                    header = (
                        companionHeader(files, path)
                        if PurePosixPath(path).suffix.lower() in SOURCE_EXTENSIONS
                        else None
                    )
                    donor = max(
                        options,
                        key=lambda candidate: donorScore(objects, candidate, path, header, distances, shape_cache),
                    )
                    score = donorScore(objects, donor, path, header, distances, shape_cache)
                    entries.append(
                        {
                            "tree": tree,
                            "path": path,
                            "blob": donor["blob"],
                            "provenance": f"unverified donor reconstruction; {score[-1]}:{donor['path']}; "
                            f"headerMatch={score[0]}; apiOverlap={score[2]}/10000; distance={-score[4]}",
                        }
                    )
                    counts["donorEntryCount"] += 1
                elif image:
                    content = imagePlaceholder(path)
                    source = "payloads/images/" + hashlib.sha256(path.encode()).hexdigest() + ".png"
                    payloads[source] = content
                    entries.append(
                        {
                            "tree": tree,
                            "path": path,
                            "source": source,
                            "sha256": hashlib.sha256(content).hexdigest(),
                            "provenance": "synthesized visible 32px placeholder; original artwork unavailable; unverified",
                        }
                    )
                    counts["placeholderEntryCount"] += 1
                else:
                    unresolved.append(
                        {
                            "tree": tree,
                            "path": path,
                            "originalBlob": entry["originalBlob"],
                            "reason": "no surviving donor with matching basename or class",
                        }
                    )
            for path, replacement in sorted(chosen_upstream.items()):
                if path in applied_upstream:
                    continue
                replaces_existing = replacement.get("replaceExisting") and path in files
                adds_missing = replacement.get("add") and path not in files
                if not (replaces_existing or adds_missing):
                    continue
                prefix = replacement.get("whenPrefix")
                if prefix and not any(candidate.startswith(prefix) for candidate in files):
                    continue
                payloads[replacement["source"]] = replacement["_content"]
                entries.append(
                    {
                        key: value
                        for key, value in {**replacement, "tree": tree}.items()
                        if key not in ("_content", "whenPrefix")
                    }
                )
                counts["upstreamEntryCount"] += 1
        entries.extend(compatibility.values())
        counts["compatibilityEntryCount"] = len(compatibility)
    entries.sort(key=lambda entry: (entry["tree"], entry["path"]))
    unresolved.sort(key=lambda entry: (entry["tree"], entry["path"]))
    return (
        {"schemaVersion": 1, "entries": entries},
        {
            "schemaVersion": 1,
            "status": "proposals-unverified",
            **counts,
            "proposedEntryCount": len(entries),
            "unresolvedCount": len(unresolved),
            "unresolved": unresolved,
        },
        payloads,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--donor", action="append", dest="donors")
    args = parser.parse_args(argv)
    try:
        manifest, report, payloads = proposeOverrides(args.repo_root, recovery.readJson(args.catalog), args.donors)
        for path, content in sorted(payloads.items()):
            target = args.output.parent / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        recovery.writeJson(args.output, manifest)
        recovery.writeJson(args.report, report)
        print(
            json.dumps({key: value for key, value in report.items() if key != "unresolved"}, sort_keys=True, indent=2)
        )
        return 0
    except (recovery.RecoveryError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"Recovery proposals blocked: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
