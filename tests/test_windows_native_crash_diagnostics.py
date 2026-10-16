# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

"""Source contracts for the native-only Windows numerical crash diagnostics."""

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class WindowsNativeCrashDiagnosticsTest(unittest.TestCase):
    def testFatalExceptionDeliveryIsPreserved(self):
        header = (ROOT / "tests/unit/native_crash_diagnostics.h").read_text()
        self.assertIn("AddVectoredExceptionHandler(1, logWindowsCrash)", header)
        self.assertIn("return EXCEPTION_CONTINUE_SEARCH;", header)
        for forbidden in (
            "EXCEPTION_EXECUTE_HANDLER",
            "EXCEPTION_CONTINUE_EXECUTION",
            "ExitProcess",
            "TerminateProcess",
        ):
            self.assertNotIn(forbidden, header)
        self.assertNotIn("RemoveVectoredExceptionHandler", header)

    def testBothBinariesInstallBeforePythonInitialization(self):
        for name in ("test_core.cpp", "test_navigation_search.cpp"):
            with self.subTest(binary=name):
                source = (ROOT / "tests/unit" / name).read_text()
                main = source[source.index("int main() {") :]
                self.assertLess(
                    main.index("native_test_diagnostics::installWindowsCrashDiagnostics();"),
                    main.index("pybind11::scoped_interpreter guard{};"),
                )

    def testCoreSearchSubphasesKeepAssertionsAndFlush(self):
        source = (ROOT / "tests/unit/test_core.cpp").read_text()
        start = source.index("void test_pathfinder_find_path_without_obstacles() {")
        end = source.index("void test_pathfinder_rejects_overflowing_routes()", start)
        case = source[start:end]
        self.assertEqual(case.count("expect_true("), 4)
        for phase in ("synchronous search", "lazy task construction", "worker execution and posted continuation"):
            self.assertIn(f'"[core-pathfinder] ENTER {phase}" << std::endl;', case)
            self.assertIn(f'"[core-pathfinder] EXIT {phase}" << std::endl;', case)

    def testRecordReportsNumericalCodeAndFaultLocationWithoutNewLinkDependencies(self):
        header = (ROOT / "tests/unit/native_crash_diagnostics.h").read_text()
        for field in ("code=0x%08lx", "module=%s", "offset=0x%llx", "rip=0x%llx", "rax=0x%llx", "rdx=0x%llx"):
            self.assertIn(field, header)
        self.assertIn("GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT", header)
        self.assertIn("std::fflush(stderr);", header)
        self.assertIn("#if defined(_WIN32)", header)
        self.assertNotIn("DbgHelp", header)


if __name__ == "__main__":
    unittest.main()
