"""[EPIC_05][STORY_03][SUBSTORY_02] Direct RenderCopy call-site migration guard.

STORY_03 introduced the GUI rendering facade (CRenderContext, SUBSTORY_01) and
migrated every direct ``SDL_RenderCopy`` / ``SDL_RenderCopyEx`` call site onto it
(renderBackground, animation, map/tile, widgets, panels, and the text manager --
all of which now render through ``CRenderContext::copy`` / ``copyEx``).

This test certifies and locks the migration's acceptance criterion: the approved
low-level rendering file is the ONLY remaining direct user of the raw SDL copy
entry points. It is a pure source scan -- it needs no built ``_game`` extension --
so it runs in the fast ``tests/`` discovery step and fails fast if a future change
reintroduces a direct call outside the facade.

SUBSTORY_03 adds the same guard to the shared content validator so the ``validate``
CI job enforces it too; this unit test is the standalone, developer-facing mirror.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

# Explicit, reviewed allowlist: files permitted to call the raw SDL copy entry
# points. Only the rendering facade wraps them; everything else must route through
# CRenderContext. Keep this list minimal and justify every addition in review.
APPROVED_FILES = {
    "src/gui/CRenderContext.cpp",
}

# Match the actual call sites (identifier immediately followed by an open paren),
# not incidental prose, so a comment that merely names the function is not flagged.
_RENDER_COPY_CALL = re.compile(r"\bSDL_RenderCopy(?:Ex)?\s*\(")

_SOURCE_SUFFIXES = {".cpp", ".h", ".hpp", ".cc", ".cxx", ".c"}


def _iter_source_files():
    for path in sorted(SRC_ROOT.rglob("*")):
        if path.is_file() and path.suffix in _SOURCE_SUFFIXES:
            yield path


def _direct_rendercopy_users():
    """Return {repo_relative_path: [line_numbers]} for direct SDL_RenderCopy* calls."""
    hits = {}
    for path in _iter_source_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = [i + 1 for i, line in enumerate(text.splitlines()) if _RENDER_COPY_CALL.search(line)]
        if lines:
            hits[path.relative_to(REPO_ROOT).as_posix()] = lines
    return hits


class RenderFacadeMigrationTest(unittest.TestCase):
    def test_direct_rendercopy_calls_confined_to_approved_files(self):
        # Acceptance: approved low-level rendering files are the only remaining
        # direct SDL_RenderCopy / SDL_RenderCopyEx users. Any call outside the
        # allowlist means a call site bypassed the CRenderContext facade.
        users = _direct_rendercopy_users()
        offenders = {path: lines for path, lines in users.items() if path not in APPROVED_FILES}
        self.assertEqual(
            {},
            offenders,
            "Direct SDL_RenderCopy* calls must route through the CRenderContext facade; "
            f"unmigrated call sites found: {offenders}",
        )

    def test_approved_facade_still_owns_the_raw_calls(self):
        # Guard against the allowlist drifting: the facade must actually still be
        # the wrapper (so the migration target exists and the allowlist is real).
        users = _direct_rendercopy_users()
        self.assertIn(
            "src/gui/CRenderContext.cpp",
            users,
            "Expected CRenderContext to own the raw SDL_RenderCopy* calls; the facade may have moved.",
        )
        for approved in APPROVED_FILES:
            self.assertTrue((REPO_ROOT / approved).is_file(), f"Approved file missing: {approved}")


if __name__ == "__main__":
    unittest.main()
