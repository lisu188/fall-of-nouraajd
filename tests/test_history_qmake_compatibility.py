# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import hashlib
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from scripts.history_qmake_compatibility import PROVIDER_INCLUDE, recipeForSource


class ProviderCompatibilityTests(unittest.TestCase):
    def testOriginalProviderLayoutAddsOnlyTheReviewedArgument(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "object/CAnimatedObject.cpp"
            header = root / "provider/CAnimationProvider.h"
            source.parent.mkdir()
            header.parent.mkdir()
            source.write_text('#include "CAnimationProvider.h"\n')
            header.write_text("#pragma once\n")
            hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in (source, header)]
            recipe = {"id": "historical", "qmakeArguments": ["QMAKE_CXX=g++-5"]}
            with patch(
                "scripts.history_qmake_compatibility.PROVIDER_INPUTS",
                dict(zip((str(path.relative_to(root)) for path in (source, header)), hashes)),
            ):
                actual = recipeForSource(recipe, root)
                self.assertIs(recipeForSource(actual, root), actual)
            self.assertEqual(actual["qmakeArguments"], ["QMAKE_CXX=g++-5", PROVIDER_INCLUDE])
            self.assertEqual(recipe["qmakeArguments"], ["QMAKE_CXX=g++-5"])
            self.assertEqual(hashes, [hashlib.sha256(path.read_bytes()).hexdigest() for path in (source, header)])

    def testEarlierLayoutAndQualifiedIncludesKeepTheirRecipeIdentity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            recipe = {"id": "historical", "qmakeArguments": []}
            self.assertIs(recipeForSource(recipe, root), recipe)
            (root / "provider").mkdir()
            (root / "provider/CAnimationProvider.h").write_text("#pragma once\n")
            (root / "object").mkdir()
            (root / "object/CAnimatedObject.cpp").write_text('#include "provider/CAnimationProvider.h"\n')
            self.assertIs(recipeForSource(recipe, root), recipe)


if __name__ == "__main__":
    unittest.main()
