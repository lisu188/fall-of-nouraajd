# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

"""Start a test MCP process with one seed before its first game session.

Octobogz uses seed 100, matching the native deterministic hunt replay. Normal
MCP startup remains unseeded; this launcher never reseeds save/reload operations.
"""

import argparse
import importlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MAX_SEED = (1 << 32) - 1


def validateSeed(seed):
    if type(seed) is not int or not 0 <= seed <= MAX_SEED:
        raise ValueError("The MCP fixture seed must be an unsigned 32-bit integer")


def runSeededMcp(seed, arguments, *, mcp_module=None):
    validateSeed(seed)
    if mcp_module is None:
        mcp_module = importlib.import_module("mcp")
    server_type = mcp_module.EngineMcpServer
    import_modules = server_type._importModules
    seeded = False

    def importSeededModules(server):
        nonlocal seeded
        import_modules(server)
        if seeded:
            return
        native = server._game_module
        seed_random = getattr(native, "_seedRandomForTests", None)
        if not callable(seed_random):
            raise RuntimeError("The compiled _game module lacks _seedRandomForTests; rebuild the current test binary")
        loop = native.event_loop.instance()
        if not loop.isMainThread():
            raise RuntimeError("The MCP fixture must seed on the engine owner thread before loading a game")
        seed_random(seed)
        seeded = True
        print("MCP fixture random seed " + json.dumps({"seed": seed}), file=sys.stderr, flush=True)

    with patch.object(server_type, "_importModules", importSeededModules):
        with patch.object(sys, "argv", [str(ROOT / "mcp.py"), *arguments]):
            return mcp_module.main()


def main(argv=None, *, mcp_module=None):
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--fixture-seed", required=True, type=int)
    options, arguments = parser.parse_known_args(argv)
    try:
        validateSeed(options.fixture_seed)
    except ValueError as exc:
        parser.error(str(exc))
    return runSeededMcp(options.fixture_seed, arguments, mcp_module=mcp_module)


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
