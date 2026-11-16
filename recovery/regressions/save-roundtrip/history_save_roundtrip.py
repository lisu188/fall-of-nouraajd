#!/usr/bin/env python3
"""Run a recovered game twice and verify its save survives loading unchanged."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def normalizeSave(value):
    result = json.loads(json.dumps(value))
    for coordinates in result["map"].values():
        if isinstance(coordinates, list):
            coordinates.sort()
    return result


def runGame(snapshot_dir, executable, output_dir, preload, timeout):
    output_dir.mkdir()
    report_path = output_dir / "startup.json"
    environment = dict(os.environ)
    environment.update(
        {
            "GAME_RECOVERY_SMOKE_REPORT": str(report_path),
            "LIBGL_ALWAYS_SOFTWARE": "1",
            "QT_OPENGL": "software",
            "QT_X11_NO_MITSHM": "1",
            "SDL_VIDEODRIVER": "x11",
            "SDL_AUDIODRIVER": "dummy",
            "SDL_RENDER_DRIVER": "software",
        }
    )
    if preload:
        environment["LD_PRELOAD"] = str(preload)
    command = ["xvfb-run", "-a", "--server-args=-screen 0 1920x1080x24", str(executable)]
    with (output_dir / "startup.log").open("wb") as stream:
        process = subprocess.run(
            command, cwd=snapshot_dir, env=environment, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout
        )
    report = json.loads(report_path.read_text()) if report_path.exists() else {}
    ready = (
        process.returncode == 0
        and report.get("status") == "ready"
        and all(report.get("checks", {}).get(name) for name in ("map", "player", "eventLoop", "renderedFrame"))
    )
    return {"command": command, "returnCode": process.returncode, "ready": ready}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir", type=Path, required=True, help="Disposable restored runtime source directory")
    parser.add_argument(
        "--executable", type=Path, required=True, help="Historical game linked with the startup observer"
    )
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory for compact regression evidence")
    parser.add_argument("--preload", type=Path, help="Optional recorded Windows path compatibility library")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    if os.name != "posix" or not shutil.which("xvfb-run") or not shutil.which("xauth"):
        parser.error("The real game regression requires xvfb-run and xauth on an isolated Linux display")
    snapshot_dir = args.snapshot_dir.resolve(strict=True)
    executable = args.executable.resolve(strict=True)
    output_dir = args.output_dir.absolute()
    preload = args.preload.resolve(strict=True) if args.preload else None
    if not snapshot_dir.is_dir() or not executable.is_file():
        parser.error("Snapshot directory and executable must exist")
    if output_dir.exists() or output_dir.is_symlink():
        parser.error("Output directory must be new")
    save_dir = snapshot_dir / "save"
    if save_dir.is_symlink() or (save_dir.exists() and (not save_dir.is_dir() or any(save_dir.iterdir()))):
        parser.error(
            "Refusing to overwrite pre-existing save data; use a disposable snapshot with an empty save directory"
        )
    output_dir.mkdir(parents=True)
    save_dir.mkdir(exist_ok=True)
    save_path = save_dir / "game.sav"
    proof = {"schemaVersion": 1, "snapshotDirectory": str(snapshot_dir), "executable": str(executable), "runs": []}
    try:
        saved = []
        for number in (1, 2):
            run = runGame(snapshot_dir, executable, output_dir / f"run-{number}", preload, args.timeout)
            proof["runs"].append(run)
            if not run["ready"]:
                raise AssertionError(f"Game run {number} did not render and exit cleanly")
            data = save_path.read_bytes()
            (output_dir / f"save-{number}.json").write_bytes(data)
            value = json.loads(data)
            if not value.get("state", {}).get("Player"):
                raise AssertionError("Save did not contain the real player")
            run["saveSha256"] = hashlib.sha256(data).hexdigest()
            saved.append(value)
        proof["checks"] = {
            "bothRunsReadyAndClean": all(run["ready"] for run in proof["runs"]),
            "completeSaveRoundtrip": normalizeSave(saved[0]) == normalizeSave(saved[1]),
        }
        if not all(proof["checks"].values()):
            raise AssertionError("Loading and saving changed the persisted map or creature state")
        proof["status"] = "success"
    except (AssertionError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        proof.update({"status": "failed", "reason": str(error)})
    finally:
        (output_dir / "regression.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof, indent=2))
    return 0 if proof.get("status") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
