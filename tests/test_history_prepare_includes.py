# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Portable snapshot preparation preserves originals and accepts only recorded literal edits."""

import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from scripts import history_prepare_includes as portable
from scripts import history_source_prep as preparation


class HistoricalPortableIncludeTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="history-portable-includes-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "original"
        (self.source / "view").mkdir(parents=True)
        self.original = b'#include "view\\playerlistview.h"\r\nPlayerListView *view;\r\n'
        (self.source / "view/gamescene.cpp").write_bytes(self.original)
        (self.source / "view/playerlistview.h").write_text("struct PlayerListView {};\n")
        prepared = self.root / "prepared"
        shutil.copytree(self.source, prepared)
        self.proof = preparation.prepareSources(prepared, self.root / "logs", {}, {}, None)
        self.expected = (prepared / "view/gamescene.cpp").read_bytes()

    def testPortableScriptReplaysOnlyRecordedEditsOnASeparateBuildCopy(self):
        build = self.root / "build"
        shutil.copytree(self.source, build)
        (build / "recovery").mkdir()
        (build / "recovery/prepare_build_sources.py").write_bytes(Path(portable.__file__).read_bytes())
        (build / "recovery/source-preparation.json").write_text(json.dumps(self.proof))
        result = subprocess.run(
            [sys.executable, str(build / "recovery/prepare_build_sources.py")], capture_output=True, text=True
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(self.expected, (build / "view/gamescene.cpp").read_bytes())
        self.assertEqual(self.original, (self.source / "view/gamescene.cpp").read_bytes())
        self.assertEqual([], portable.applyRecordedIncludes(build, self.proof))

    def testChangedOriginalOrExpectedOutputRejectsAllWrites(self):
        original = self.source / "view/gamescene.cpp"
        original.write_bytes(self.original + b"// user modification\n")
        with self.assertRaisesRegex(ValueError, "preimage"):
            portable.applyRecordedIncludes(self.source, self.proof)
        self.assertEqual(self.original + b"// user modification\n", original.read_bytes())
        original.write_bytes(self.original)
        changed = copy.deepcopy(self.proof)
        changed["identity"]["includeSeparators"][0]["afterSha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "postimage"):
            portable.applyRecordedIncludes(self.source, changed)
        self.assertEqual(self.original, original.read_bytes())

    def testEscapingPathsAndNonSeparatorChangesAreRejected(self):
        for name in ("../external.cpp", "/tmp/external.cpp", "C:\\external.cpp"):
            with self.subTest(path=name):
                changed = copy.deepcopy(self.proof)
                changed["identity"]["includeSeparators"][0]["path"] = name
                with self.assertRaises(ValueError):
                    portable.applyRecordedIncludes(self.source, changed)
        changed = copy.deepcopy(self.proof)
        changed["identity"]["includeSeparators"][0]["includes"][0]["preparedInclude"] = "different.h"
        with self.assertRaisesRegex(ValueError, "literal"):
            portable.applyRecordedIncludes(self.source, changed)

    def testSymlinkedSourceOrHeaderCannotEscapeTheBuildCopy(self):
        path = self.source / "view/gamescene.cpp"
        outside = self.root / "external.cpp"
        outside.write_bytes(self.original)
        path.unlink()
        path.symlink_to(outside)
        with self.assertRaises(ValueError):
            portable.applyRecordedIncludes(self.source, self.proof)
        path.unlink()
        path.write_bytes(self.original)
        header = self.source / "view/playerlistview.h"
        outside = self.root / "external.h"
        outside.write_bytes(header.read_bytes())
        header.unlink()
        header.symlink_to(outside)
        with self.assertRaises(ValueError):
            portable.applyRecordedIncludes(self.source, self.proof)
        self.assertEqual(self.original, path.read_bytes())

    def testPortableSemanticsArePartOfPreparationIdentity(self):
        self.assertEqual(
            hashlib.sha256(Path(portable.__file__).read_bytes()).hexdigest(),
            self.proof["identity"]["includeReplaySha256"],
        )


if __name__ == "__main__":
    unittest.main()
