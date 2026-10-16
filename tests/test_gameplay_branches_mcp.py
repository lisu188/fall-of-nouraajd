# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Stable per-route/per-class native MCP cases; discovery alone is not gameplay evidence."""

from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import sys
from time import monotonic
import traceback
import unittest
import uuid
from unittest.mock import patch

from tests.gameplay_branch_driver import GameplayBranchDriver, ROOT, caseSeed


def receiptProvenance(*, required=False):
    platform = {"linux": "linux", "win32": "windows"}.get(sys.platform)
    if platform is None:
        raise ValueError("Unsupported native branch receipt platform: " + sys.platform)
    result = {
        "platform": platform,
        "head": os.environ.get("GAME_MCP_BRANCH_HEAD"),
        "prHead": os.environ.get("GAME_MCP_BRANCH_PR_HEAD"),
    }
    if required and any(not isinstance(result[key], str) or not result[key].strip() for key in ("head", "prHead")):
        raise ValueError("Required native branch receipts need both checkout and PR head provenance")
    return result


@lru_cache(maxsize=16)
def verifyCopiedSources(build_dir, build_config, sources):
    for name in sources:
        relative = Path(name)
        if relative.parts[0] != "res":
            continue
        copied = Path(build_dir) / Path(*relative.parts[1:])
        alternate = Path(build_dir) / (build_config or "Release") / Path(*relative.parts[1:])
        candidate = copied if copied.is_file() else alternate
        if not candidate.is_file():
            raise AssertionError(f"Current copied resource is missing: {copied}")
        if hashlib.sha256((ROOT / relative).read_bytes()).digest() != hashlib.sha256(candidate.read_bytes()).digest():
            raise AssertionError(f"Copied resource is stale: {candidate}; rebuild from the tested head")


class GameplayBranchMcpTest(unittest.TestCase):
    def runCase(self, case, class_id):
        import test as harness

        required = os.environ.get("GAME_MCP_BRANCH_REQUIRED") == "1"
        if type(self).__module__ not in {"test", "__main__"} and not required:
            self.skipTest("Run exhaustive routes through test.py --suite mcp-branches")
        provenance = receiptProvenance(required=required)
        extension_dirs = (harness.build_dir, *harness.extension_dirs)
        if not any(list(path.glob("_game*.pyd")) + list(path.glob("_game*.so")) for path in extension_dirs):
            message = "Current _game extension required for the exhaustive MCP gameplay branch matrix"
            if required:
                self.fail(message)
            self.skipTest(message)
        verifyCopiedSources(str(harness.build_dir), harness.build_config, case.sources)
        identifier = f"{case.id}-{class_id}-{uuid.uuid4().hex}"
        output_dir = harness.TEST_OUTPUT_DIR / "mcp-branches"
        output_dir.mkdir(parents=True, exist_ok=True)
        trace_path = output_dir / (identifier + ".trace.jsonl")
        action_path = output_dir / (identifier + ".actions.jsonl")
        receipt_path = output_dir / (identifier + ".receipt.json")
        preference_path = harness.build_dir / (identifier + ".preferences.json")
        seed = caseSeed(case.id, class_id)
        action_path.write_text(json.dumps({"case": case.id, "class": class_id, "seed": seed}) + "\n", encoding="utf-8")
        environment = os.environ.copy()
        environment.update(
            SDL_VIDEODRIVER="dummy",
            SDL_AUDIODRIVER="dummy",
            SDL_RENDER_DRIVER="software",
            LIBGL_ALWAYS_SOFTWARE="1",
            GAME_UI_PREFERENCES_PATH=str(preference_path),
            GAME_PLAYTEST_TRACE="1",
            GAME_PLAYTEST_TRACE_FILE=str(trace_path),
            GAME_PLAYTEST_TRACE_RETAIN_RECENT="1",
        )
        command = [
            sys.executable,
            str(ROOT / "mcp.py"),
            "--stdio",
            "--repo-root",
            str(ROOT),
            "--build-dir",
            str(harness.build_dir),
            "--native-log-sink",
            "disabled",
            "--test-seed",
            str(seed),
        ]
        if harness.build_config:
            command.extend(("--build-config", harness.build_config))
        client = harness.McpServerTest(methodName="runTest")
        process = client._start_stdio_process(command, env=environment, map_name=case.maps[0])
        driver = None
        receipt = {
            **provenance,
            "case": case.id,
            "class": class_id,
            "seed": seed,
            "status": "failed",
            "requiredBranches": list(case.branches),
            "command": command,
            "tracePath": str(trace_path),
            "actionPath": str(action_path),
        }
        started = monotonic()
        try:
            client._initialize_stdio_mcp(process)
            session = {"proc": process, "next_request_id": 3}
            driver = GameplayBranchDriver(self, client, session, case, class_id, harness.build_dir)
            driver.trace_path, driver.action_path = trace_path, action_path
            # Starting-save subprocesses inherit the same isolated display and preference paths.
            with patch.dict(os.environ, environment):
                case.run(driver)
                driver.finish()
            receipt["status"] = "passed"
        except BaseException:
            receipt["traceback"] = traceback.format_exc()
            raise
        finally:
            if driver is not None:
                receipt.update(driver.receipt())
            receipt["seconds"] = monotonic() - started
            receipt["stderrTail"] = client._mcp_process_tail_text(process, "stderr")
            receipt["stdoutTail"] = client._mcp_process_tail_text(process, "stdout")
            try:
                client._shutdown_process(process)
            except BaseException:
                receipt["status"] = "failed"
                receipt["shutdownTraceback"] = traceback.format_exc()
                raise
            finally:
                if driver is not None:
                    driver.cleanup()
                preference_path.unlink(missing_ok=True)
                receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                print(f"MCP branch receipt: {receipt_path}", flush=True)


def installCases():
    from tests.gameplay_branch_catalog import getCases

    for case in getCases():
        for class_id in case.classes:

            def run(self, case=case, class_id=class_id):
                self.runCase(case, class_id)

            run.__name__ = f"test_{case.id}_{class_id}"
            run.__doc__ = f"{case.id}: {class_id}; {len(case.branches)} authored obligations"
            setattr(GameplayBranchMcpTest, run.__name__, run)


installCases()
