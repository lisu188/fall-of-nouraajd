#!/usr/bin/env python3
# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


class ConfigureSupplyChainTest(unittest.TestCase):
    def test_linux_configure_uses_os_pybind11_package(self):
        configure_script = (REPO_ROOT / "configure.sh").read_text()

        self.assertIn("pybind11-dev", configure_script)
        self.assertIn("python3-pip", configure_script)
        self.assertIn("python3-venv", configure_script)
        self.assertIn("python3-pil", configure_script)
        self.assertIn("black", configure_script)
        self.assertNotRegex(configure_script, re.compile(r"python3\s+-m\s+pip\s+install[^\n]*\bpybind11\b"))
        self.assertIn("dpkg-query -L pybind11-dev", configure_script)
        self.assertIn("pybind11Config.cmake was not found in the pybind11-dev package", configure_script)
        self.assertIn('-Dpybind11_DIR="${PYBIND11_DIR}"', configure_script)
        self.assertNotIn("python3 -m pybind11 --cmakedir", configure_script)

    def test_cmake_does_not_auto_load_pybind11_python_package(self):
        cmake_lists = (REPO_ROOT / "CMakeLists.txt").read_text()

        self.assertIn("find_package(pybind11 CONFIG REQUIRED)", cmake_lists)
        self.assertNotIn("COMMAND ${Python3_EXECUTABLE} -m pybind11 --cmakedir", cmake_lists)
        self.assertNotIn("list(APPEND CMAKE_PREFIX_PATH ${pybind11_cmake_dir})", cmake_lists)

    def test_windows_configure_uses_vcpkg_pybind11(self):
        configure_script = (REPO_ROOT / "configure.bat").read_text()
        vcpkg_manifest = (REPO_ROOT / "vcpkg.json").read_text()

        self.assertIn('"pybind11"', vcpkg_manifest)
        self.assertNotIn("python -m pybind11 --cmakedir", configure_script)
        self.assertNotIn("pip install --upgrade pybind11", configure_script)
        self.assertNotIn("-Dpybind11_DIR", configure_script)

    def test_workflow_actions_are_pinned_to_full_commit_shas(self):
        for workflow_path in (REPO_ROOT / ".github" / "workflows").glob("*.yml"):
            for uses in re.findall(r"uses:\s*([^\s#]+)", workflow_path.read_text()):
                self.assertRegex(uses, r"@[0-9a-f]{40}$", f"{workflow_path}: {uses}")
                self.assertNotRegex(uses, r"@v\d", f"{workflow_path}: {uses}")

    def test_workflows_do_not_install_unpinned_pybind11_or_pillow(self):
        workflow_text = "\n".join(path.read_text() for path in (REPO_ROOT / ".github" / "workflows").glob("*.yml"))
        requirements_text = (REPO_ROOT / "requirements-dev.txt").read_text()

        self.assertNotRegex(workflow_text, re.compile(r"pip\s+install[^\n]*\bpybind11\b", re.IGNORECASE))
        self.assertNotRegex(workflow_text, re.compile(r"pip\s+install[^\n]*\bpillow(?:\s|$)", re.IGNORECASE))
        self.assertIn("-r requirements-dev.txt", workflow_text)
        self.assertIn("from PIL import Image; import black", workflow_text)
        self.assertIn("import _game; import game", workflow_text)
        self.assertRegex(requirements_text, re.compile(r"^pillow==[0-9]+(?:\.[0-9]+)*$", re.MULTILINE))
        self.assertRegex(requirements_text, re.compile(r"^black==[0-9]+(?:\.[0-9]+)*$", re.MULTILINE))
        self.assertNotRegex(requirements_text, re.compile(r"^pybind11\b", re.IGNORECASE | re.MULTILINE))

    def test_temporary_multi_workbook_apply_artifacts_are_removed(self):
        self.assertFalse((REPO_ROOT / ".github" / "workflows" / "apply-multi-workbook-workflow.yml").exists())
        self.assertFalse((REPO_ROOT / ".github" / "multi-workbook-payload").exists())
        self.assertFalse((REPO_ROOT / ".github" / "multi-workbook-inspection.txt").exists())

    def test_windows_job_installs_vcpkg_when_installed_cache_is_missing(self):
        workflow_text = (REPO_ROOT / ".github" / "workflows" / "build.yml").read_text()
        match = re.search(r"(?ms)^  windows:\n(?P<body>.*?)(?=^  [A-Za-z0-9_-]+:|\Z)", workflow_text)
        self.assertIsNotNone(match)
        job_body = match.group("body")

        self.assertIn("- name: Install vcpkg deps when installed cache is missing", job_body)
        self.assertIn("id: install-missing-vcpkg-installed", job_body)
        self.assertIn("if: steps.restore-vcpkg-installed.outputs.cache-hit != 'true'", job_body)
        self.assertIn('& "$env:VCPKG_ROOT\\vcpkg.exe" install `', job_body)
        self.assertIn('"--x-install-root=$env:VCPKG_INSTALLED_DIR"', job_body)
        self.assertIn("- name: Save missing vcpkg installed tree", job_body)
        self.assertIn("key: ${{ needs.windows-deps.outputs.vcpkg-installed-cache-key }}", job_body)
        self.assertNotIn("windows-deps did not seed a valid vcpkg installed cache", job_body)

    def test_linux_coverage_job_uploads_failure_report_artifact(self):
        workflow_text = (REPO_ROOT / ".github" / "workflows" / "build.yml").read_text()
        match = re.search(r"(?ms)^  linux-coverage:\n(?P<body>.*?)(?=^  [A-Za-z0-9_-]+:|\Z)", workflow_text)
        self.assertIsNotNone(match)
        job_body = match.group("body")

        self.assertIn("- name: coverage", job_body)
        self.assertIn("- name: Upload coverage report", job_body)
        self.assertLess(job_body.index("- name: coverage"), job_body.index("- name: Upload coverage report"))
        self.assertRegex(
            job_body,
            re.compile(
                r"(?ms)- name: Upload coverage report\n"
                r"\s+if: always\(\)\n"
                r"\s+uses: actions/upload-artifact@[0-9a-f]{40}\n"
                r"\s+with:\n"
                r"\s+name: linux-coverage-report\n"
                r"\s+path: \|\n"
                r"\s+coverage/\n"
                r"\s+test/test-timings-linux-coverage\.json\n"
                r"\s+if-no-files-found: warn"
            ),
        )

    def test_linux_coverage_path_filter_matches_required_policy(self):
        workflow_text = (REPO_ROOT / ".github" / "workflows" / "build.yml").read_text()
        classifier_text = (REPO_ROOT / "scripts" / "ci_change_classifier.py").read_text()

        self.assertIn("- name: classify changed paths", workflow_text)
        self.assertIn("python3 scripts/ci_change_classifier.py", workflow_text)
        self.assertIn('"test.py"', classifier_text)
        self.assertIn('"tests/unit/*"', classifier_text)
        self.assertIn('"scripts/run_coverage.sh"', classifier_text)
        self.assertIn('"scripts/coverage_report.py"', classifier_text)
        self.assertIn('"native_plugins/*"', classifier_text)
        self.assertIn('"src/core/*"', classifier_text)
        self.assertIn('"src/gui/*"', classifier_text)
        self.assertIn('"src/handler/*"', classifier_text)
        self.assertIn('"src/object/*"', classifier_text)
        self.assertNotIn('"tests/*"', classifier_text)

    def test_run_coverage_default_line_gate_is_90_percent(self):
        run_coverage = (REPO_ROOT / "scripts" / "run_coverage.sh").read_text()

        self.assertIn('MIN_COVERAGE="${MIN_COVERAGE:-90}"', run_coverage)
        self.assertNotIn('MIN_COVERAGE="${MIN_COVERAGE:-95}"', run_coverage)


if __name__ == "__main__":
    unittest.main()
