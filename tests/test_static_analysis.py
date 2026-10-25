"""Unit tests for the compile-database static-analysis source selector."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_clang_tidy import projectSources


class StaticAnalysisSourceSelectionTest(unittest.TestCase):
    def test_excludes_dependencies_generated_files_and_external_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = [
                root / "src" / "core" / "CMap.cpp",
                root / "native_plugins" / "plugin.cpp",
                root / "vstd" / "dependency.cpp",
                root / "build" / "generated.cpp",
            ]
            for source in sources:
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text("int main() { return 0; }\n", encoding="utf-8")
            database = root / "compile_commands.json"
            database.write_text(
                json.dumps([{"directory": str(root), "file": str(source)} for source in sources]),
                encoding="utf-8",
            )

            self.assertEqual(
                projectSources(database, root),
                [root / "native_plugins" / "plugin.cpp", root / "src" / "core" / "CMap.cpp"],
            )
            self.assertEqual(
                projectSources(database, root, {"src/core/CMap.cpp"}),
                [root / "src" / "core" / "CMap.cpp"],
            )
            self.assertEqual(projectSources(database, root, set()), [])
            self.assertEqual(
                projectSources(database, root, {"src/core/CMap.hpp"}),
                [root / "native_plugins" / "plugin.cpp", root / "src" / "core" / "CMap.cpp"],
            )
            self.assertEqual(
                projectSources(database, root, {"src/core/CMap.h", "src/core/CMap.cpp"}),
                [root / "native_plugins" / "plugin.cpp", root / "src" / "core" / "CMap.cpp"],
            )

    def test_rejects_invalid_compile_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "compile_commands.json"
            database.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                projectSources(database, root)


if __name__ == "__main__":
    unittest.main()
