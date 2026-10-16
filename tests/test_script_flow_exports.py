# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ScriptFlowExportTest(unittest.TestCase):
    def callbackDeclaration(self):
        header = (ROOT / "src/handler/CScriptHandler.h").read_text(encoding="utf-8")
        start = header.index("createUiFlow(")
        start = header.index(";", start) + 1
        end = header.index("static std::unique_ptr<CScriptFlow>", start)
        declaration = header[start:end].strip()
        self.assertEqual(1, declaration.count("createCallbackFlow("))
        return declaration

    def testCallbackExportLeavesWindowsDirectObjectConsumersUnchanged(self):
        declaration = self.callbackDeclaration()
        self.assertRegex(declaration, r"#if !defined\(_WIN32\)\s+GAME_CORE_EXPORT\s+#endif")
        self.assertEqual(1, declaration.count("GAME_CORE_EXPORT"))

    @unittest.skipUnless(sys.platform.startswith("linux"), "ELF shared-library visibility regression")
    def testCallbackFactoryLinksAcrossSharedLibraryWithRealPybindArgument(self):
        compiler = shlex.split(os.environ.get("CXX", "")) or [shutil.which("g++") or shutil.which("clang++")]
        if not compiler[0] or not shutil.which(compiler[0]):
            self.skipTest("A C++ compiler is required for the isolated ELF export fixture")
        include_candidates = [Path("/usr/include"), Path("/usr/local/include")]
        try:
            import pybind11
        except ImportError:
            pass
        else:
            include_candidates.insert(0, Path(pybind11.get_include()))
        pybind_include = next((path for path in include_candidates if (path / "pybind11/pybind11.h").is_file()), None)
        if pybind_include is None:
            self.skipTest("pybind11 headers are required for the isolated ELF export fixture")
        python_include = Path(sysconfig.get_paths()["include"])
        library_dir = sysconfig.get_config_var("LIBDIR")
        library_name = sysconfig.get_config_var("LDLIBRARY")
        if not library_dir or not library_name:
            self.skipTest("Python's shared development library is unavailable")
        python_library = Path(library_dir) / library_name
        if not (python_include / "Python.h").is_file() or not python_library.is_file():
            self.skipTest("Python development headers and its shared library are required")

        declaration = self.callbackDeclaration()
        with tempfile.TemporaryDirectory(prefix="nouraajd-script-export-") as directory:
            scratch = Path(directory)
            producer = scratch / "producer.cpp"
            producer.write_text(
                '#include "callback.h"\n'
                "std::unique_ptr<CScriptFlow> CScriptHandler::createCallbackFlow(\n"
                "    pybind11::function, std::weak_ptr<CGame>) { return nullptr; }\n",
                encoding="utf-8",
            )
            consumer = scratch / "consumer.cpp"
            consumer.write_text(
                '#include "callback.h"\n'
                "int main() {\n"
                "    CScriptHandler handler;\n"
                "    return handler.createCallbackFlow(pybind11::function{}, {}) ? 1 : 0;\n"
                "}\n",
                encoding="utf-8",
            )
            # The fixture isolates visibility; no engine code or C++26 feature is replaced or compiled here.
            flags = [
                "-std=c++20",
                "-I" + str(ROOT / "src"),
                "-I" + str(pybind_include),
                "-I" + str(python_include),
            ]

            def run(command):
                return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=60)

            for exported in (True, False):
                with self.subTest(exported=exported):
                    current = declaration if exported else declaration.replace("GAME_CORE_EXPORT", "")
                    (scratch / "callback.h").write_text(
                        '#include "core/CExport.h"\n'
                        "#include <pybind11/pybind11.h>\n"
                        "#include <memory>\n"
                        "class CGame;\n"
                        "class CScriptFlow {};\n"
                        "class CScriptHandler {\npublic:\n" + current + "\n};\n",
                        encoding="utf-8",
                    )
                    library = scratch / ("libexported.so" if exported else "libhidden.so")
                    build = run(compiler + flags + ["-fPIC", "-shared", str(producer), "-o", str(library)])
                    self.assertEqual(0, build.returncode, build.stdout + build.stderr)
                    executable = scratch / ("exported-consumer" if exported else "hidden-consumer")
                    link = run(
                        compiler + flags + [str(consumer), str(library), str(python_library), "-o", str(executable)]
                    )
                    if exported:
                        self.assertEqual(0, link.returncode, link.stdout + link.stderr)
                        result = run([str(executable)])
                        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                    else:
                        self.assertNotEqual(
                            0, link.returncode, "The negative control unexpectedly exported the factory"
                        )
                        self.assertIn("undefined reference", link.stderr)
                        self.assertIn("CScriptHandler::createCallbackFlow", link.stderr)


if __name__ == "__main__":
    unittest.main()
