from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import scripts.controller_capability_probe as capability_probe

FAKE_TOKEN = "ghp_FAKESECRETTOKEN0000000000000000000000"
FAKE_URL_PASSWORD = "hunter2secret"

MINI_WORKFLOW = "\n".join(
    [
        "name: build",
        "",
        "on:",
        "  push:",
        "    branches:",
        "      - main",
        "",
        "jobs:",
        "  linux-fast:",
        "    runs-on: ubuntu-24.04",
        "    steps:",
        "      - run: echo fast",
        "  linux:",
        "    needs: linux-fast",
        "    steps:",
        "      - run: echo linux",
        "  windows:",
        "    steps:",
        "      - run: echo windows",
        "",
    ]
)


def completedProcess(args, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr=stderr)


def commandKey(args):
    return tuple(args)


class FakeRunner:
    """Dispatch subprocess.run calls to canned results keyed by the command prefix."""

    def __init__(self, responses, default=None):
        self.responses = responses
        self.default = default
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append(list(args))
        for prefix, response in self.responses.items():
            if tuple(args[: len(prefix)]) == prefix:
                if isinstance(response, BaseException):
                    raise response
                return completedProcess(args, *response)
        if isinstance(self.default, BaseException):
            raise self.default
        if self.default is not None:
            return completedProcess(args, *self.default)
        raise AssertionError(f"unexpected command in test: {args}")


GIT_OK_RESPONSES = {
    ("git", "--version"): (0, "git version 2.43.0\n", ""),
    ("git", "rev-parse", "--is-inside-work-tree"): (0, "true\n", ""),
    ("git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"): (0, "origin/main\n", ""),
    ("git", "ls-remote", "--exit-code", "origin", "HEAD"): (0, "abcdef\tHEAD\n", ""),
    ("git", "worktree", "list", "--porcelain"): (0, "worktree /repo\nHEAD abcdef\n\n", ""),
}

GH_OK_RESPONSES = {
    ("gh", "--version"): (0, "gh version 2.40.0 (2024-01-01)\n", ""),
    ("gh", "auth", "status"): (0, "github.com: Logged in as octocat\n", ""),
    ("gh", "api", "rate_limit"): (0, "{}\n", ""),
}


class RepositorySectionTest(unittest.TestCase):
    def probe(self, runner):
        with unittest.mock.patch.object(capability_probe.subprocess, "run", runner):
            return capability_probe.probeRepositorySection(Path("/repo"), timeout=5.0)

    def test_all_repository_fields_available_with_healthy_git(self):
        section = self.probe(FakeRunner(dict(GIT_OK_RESPONSES)))
        for field_name in ("gitPresent", "insideWorkTree", "defaultBranch", "remoteReachable", "worktreeSupport"):
            self.assertEqual(section[field_name]["status"], "available", field_name)
        self.assertIn("origin/main", section["defaultBranch"]["evidence"])

    def test_missing_git_degrades_to_actionable_fields_without_traceback(self):
        section = self.probe(FakeRunner({}, default=FileNotFoundError("git")))
        self.assertEqual(section["gitPresent"]["status"], "unavailable")
        self.assertIn("install git", section["gitPresent"]["evidence"])
        self.assertEqual(section["remoteReachable"]["status"], "unknown")
        self.assertIn("not probed", section["remoteReachable"]["evidence"])

    def test_remote_timeout_reports_unknown_not_unavailable(self):
        responses = dict(GIT_OK_RESPONSES)
        responses[("git", "ls-remote", "--exit-code", "origin", "HEAD")] = subprocess.TimeoutExpired(
            cmd="git ls-remote", timeout=5.0
        )
        section = self.probe(FakeRunner(responses))
        self.assertEqual(section["remoteReachable"]["status"], "unknown")
        self.assertIn("timed out", section["remoteReachable"]["evidence"])

    def test_unreachable_remote_reports_unavailable_with_reason(self):
        responses = dict(GIT_OK_RESPONSES)
        responses[("git", "ls-remote", "--exit-code", "origin", "HEAD")] = (
            128,
            "",
            "fatal: could not read from remote repository\n",
        )
        section = self.probe(FakeRunner(responses))
        self.assertEqual(section["remoteReachable"]["status"], "unavailable")
        self.assertIn("could not read from remote", section["remoteReachable"]["evidence"])

    def test_git_without_worktree_subcommand_reports_unsupported(self):
        responses = dict(GIT_OK_RESPONSES)
        responses[("git", "worktree", "list", "--porcelain")] = (
            1,
            "",
            "git: 'worktree' is not a git command. See 'git --help'.\n",
        )
        section = self.probe(FakeRunner(responses))
        self.assertEqual(section["worktreeSupport"]["status"], "unsupported")


class GithubSectionTest(unittest.TestCase):
    def probe(self, runner, which_result="/usr/bin/gh"):
        with unittest.mock.patch.object(capability_probe.shutil, "which", lambda name: which_result):
            with unittest.mock.patch.object(capability_probe.subprocess, "run", runner):
                return capability_probe.probeGithubSection(timeout=5.0)

    def test_absent_gh_cli_is_graceful_and_actionable(self):
        section = self.probe(FakeRunner({}), which_result=None)
        self.assertEqual(section["ghCli"]["status"], "unavailable")
        self.assertIn("gh not found on PATH", section["ghCli"]["evidence"])
        self.assertEqual(section["ghAuth"]["status"], "unknown")
        self.assertEqual(section["apiReachable"]["status"], "unknown")

    def test_authenticated_gh_reports_available_fields(self):
        section = self.probe(FakeRunner(dict(GH_OK_RESPONSES)))
        self.assertEqual(section["ghCli"]["status"], "available")
        self.assertEqual(section["ghAuth"]["status"], "available")
        self.assertEqual(section["apiReachable"]["status"], "available")

    def test_unauthenticated_gh_reports_unavailable_auth(self):
        responses = dict(GH_OK_RESPONSES)
        responses[("gh", "auth", "status")] = (
            1,
            "",
            "You are not logged into any GitHub hosts. To log in, run: gh auth login\n",
        )
        section = self.probe(FakeRunner(responses))
        self.assertEqual(section["ghAuth"]["status"], "unavailable")
        self.assertIn("not logged into any GitHub hosts", section["ghAuth"]["evidence"])

    def test_blocked_api_reports_unavailable_with_partial_metadata(self):
        responses = dict(GH_OK_RESPONSES)
        responses[("gh", "api", "rate_limit")] = (1, "", "HTTP 403: proxy blocked api.github.com\n")
        section = self.probe(FakeRunner(responses))
        self.assertEqual(section["ghCli"]["status"], "available")
        self.assertEqual(section["apiReachable"]["status"], "unavailable")
        self.assertIn("HTTP 403", section["apiReachable"]["evidence"])

    def test_gh_output_tokens_and_credential_urls_are_redacted(self):
        responses = dict(GH_OK_RESPONSES)
        responses[("gh", "auth", "status")] = (
            0,
            f"github.com: Logged in as octocat (token {FAKE_TOKEN}) via https://user:{FAKE_URL_PASSWORD}@github.com\n",
            "",
        )
        section = self.probe(FakeRunner(responses))
        dumped = json.dumps(section)
        self.assertNotIn(FAKE_TOKEN, dumped)
        self.assertNotIn(FAKE_URL_PASSWORD, dumped)
        self.assertIn("REDACTED", dumped)


class CiSectionTest(unittest.TestCase):
    def test_missing_workflow_file_is_actionable_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            section = capability_probe.probeCiSection(Path(tmp))
        self.assertEqual(section["buildWorkflowPresent"]["status"], "unavailable")
        self.assertEqual(section["requiredJobs"]["status"], "unavailable")
        self.assertIn("build.yml", section["requiredJobs"]["evidence"])

    def test_job_names_parsed_from_workflow_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflowPath = Path(tmp) / ".github" / "workflows" / "build.yml"
            workflowPath.parent.mkdir(parents=True)
            workflowPath.write_text(MINI_WORKFLOW, encoding="utf-8")
            section = capability_probe.probeCiSection(Path(tmp))
        self.assertEqual(section["buildWorkflowPresent"]["status"], "available")
        self.assertEqual(section["requiredJobs"]["status"], "available")
        self.assertEqual(section["requiredJobs"]["evidence"], "jobs: linux, linux-fast, windows")

    def test_real_repository_workflow_jobs_are_parsed(self):
        repoRoot = Path(__file__).resolve().parents[1]
        workflowPath = repoRoot / ".github" / "workflows" / "build.yml"
        jobNames = capability_probe.parseWorkflowJobNames(workflowPath.read_text(encoding="utf-8"))
        for expected in ("linux-fast", "linux", "windows-deps", "windows"):
            self.assertIn(expected, jobNames)


class ToolchainSectionTest(unittest.TestCase):
    def test_missing_tool_is_actionable_unavailable(self):
        with unittest.mock.patch.object(capability_probe.shutil, "which", lambda name: None):
            with unittest.mock.patch.object(capability_probe, "resolveExecutable", lambda name: None):
                section = capability_probe.probeToolchainSection(timeout=5.0, platformName="linux")
        self.assertEqual(section["black"]["status"], "unavailable")
        self.assertIn("install it", section["black"]["evidence"])
        self.assertEqual(section["xvfb-run"]["status"], "unavailable")

    def test_linux_only_tools_are_unsupported_on_other_platforms(self):
        with unittest.mock.patch.object(capability_probe.shutil, "which", lambda name: f"/usr/bin/{name}"):
            with unittest.mock.patch.object(
                capability_probe.subprocess, "run", FakeRunner({}, default=(0, "v1\n", ""))
            ):
                section = capability_probe.probeToolchainSection(timeout=5.0, platformName="win32")
        self.assertEqual(section["xvfb-run"]["status"], "unsupported")
        self.assertEqual(section["xauth"]["status"], "unsupported")
        self.assertIn("win32", section["xvfb-run"]["evidence"])
        self.assertEqual(section["cmake"]["status"], "available")

    def test_tool_version_timeout_degrades_to_unknown(self):
        timeoutError = subprocess.TimeoutExpired(cmd="cmake --version", timeout=5.0)
        with unittest.mock.patch.object(capability_probe.shutil, "which", lambda name: f"/usr/bin/{name}"):
            with unittest.mock.patch.object(capability_probe.subprocess, "run", FakeRunner({}, default=timeoutError)):
                section = capability_probe.probeToolchainSection(timeout=5.0, platformName="linux")
        self.assertEqual(section["cmake"]["status"], "unknown")
        self.assertIn("timed out", section["cmake"]["evidence"])
        self.assertEqual(section["pythonVersion"]["status"], "available")


class BuildSectionTest(unittest.TestCase):
    def test_missing_build_dirs_do_not_attempt_import(self):
        runner = FakeRunner({})
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch.object(capability_probe.subprocess, "run", runner):
                section = capability_probe.probeBuildSection(Path(tmp), timeout=5.0)
        self.assertEqual(section["buildDirs"]["status"], "unavailable")
        self.assertIn("build the _game target", section["buildDirs"]["evidence"])
        self.assertEqual(section["gameModuleImportable"]["status"], "unavailable")
        self.assertEqual(runner.calls, [])

    def test_import_failure_reports_unavailable_with_reason(self):
        importError = (1, "", "ModuleNotFoundError: No module named '_game'\n")
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "cmake-build-release").mkdir()
            with unittest.mock.patch.object(capability_probe.subprocess, "run", FakeRunner({}, default=importError)):
                section = capability_probe.probeBuildSection(Path(tmp), timeout=5.0)
        self.assertEqual(section["buildDirs"]["status"], "available")
        self.assertEqual(section["gameModuleImportable"]["status"], "unavailable")
        self.assertIn("ModuleNotFoundError", section["gameModuleImportable"]["evidence"])

    def test_import_success_reports_available_via_release_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "cmake-build-debug").mkdir()
            (Path(tmp) / "cmake-build-release").mkdir()
            with unittest.mock.patch.object(capability_probe.subprocess, "run", FakeRunner({}, default=(0, "", ""))):
                section = capability_probe.probeBuildSection(Path(tmp), timeout=5.0)
        self.assertEqual(section["gameModuleImportable"]["status"], "available")
        self.assertIn("cmake-build-release", section["gameModuleImportable"]["evidence"])


class AgentSectionTest(unittest.TestCase):
    def test_env_marker_values_are_never_included(self):
        environ = {"CI": FAKE_URL_PASSWORD, "GITHUB_TOKEN": FAKE_TOKEN}
        section = capability_probe.probeAgentSection(environ=environ, platformName="linux")
        dumped = json.dumps(section)
        self.assertEqual(section["envMarkers"]["CI"]["status"], "available")
        self.assertEqual(section["envMarkers"]["GITHUB_TOKEN"]["status"], "available")
        self.assertEqual(section["envMarkers"]["GH_TOKEN"]["status"], "unavailable")
        self.assertNotIn(FAKE_TOKEN, dumped)
        self.assertNotIn(FAKE_URL_PASSWORD, dumped)


class SnapshotTest(unittest.TestCase):
    def buildMockedSnapshot(self, repoRoot, now=None):
        responses = dict(GIT_OK_RESPONSES)
        responses.update(GH_OK_RESPONSES)
        runner = FakeRunner(responses, default=(0, "tool version 1.0\n", ""))
        with unittest.mock.patch.object(capability_probe.shutil, "which", lambda name: f"/usr/bin/{name}"):
            with unittest.mock.patch.object(capability_probe.subprocess, "run", runner):
                return capability_probe.buildSnapshot(
                    repoRoot, timeout=5.0, now=now, environ={"CI": "1"}, platformName="linux"
                )

    def test_two_runs_produce_identical_deterministic_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = self.buildMockedSnapshot(Path(tmp))
            second = self.buildMockedSnapshot(Path(tmp))
        firstDump = json.dumps(first, indent=2, sort_keys=True)
        secondDump = json.dumps(second, indent=2, sort_keys=True)
        self.assertEqual(firstDump, secondDump)
        self.assertNotIn("generatedAt", first)

    def test_now_flag_is_recorded_verbatim(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = self.buildMockedSnapshot(Path(tmp), now="2026-07-02T00:00:00Z")
        self.assertEqual(snapshot["generatedAt"], "2026-07-02T00:00:00Z")

    def assertLeafFields(self, fields, path):
        for key in fields:
            value = fields[key]
            self.assertIsInstance(value, dict, f"{path}.{key}")
            if set(value) == {"evidence", "status"}:
                self.assertIn(value["status"], capability_probe.ALLOWED_STATUSES, f"{path}.{key}")
                self.assertIsInstance(value["evidence"], str, f"{path}.{key}")
                self.assertLessEqual(len(value["evidence"]), capability_probe.MAX_EVIDENCE_CHARS, f"{path}.{key}")
            else:
                self.assertLeafFields(value, f"{path}.{key}")

    def test_schema_is_stable_with_sorted_sections_and_leaf_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = self.buildMockedSnapshot(Path(tmp))
        self.assertEqual(sorted(snapshot["sections"]), list(capability_probe.SECTION_NAMES))
        for sectionName, fields in snapshot["sections"].items():
            self.assertLeafFields(fields, sectionName)

    def test_section_filter_limits_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            responses = dict(GIT_OK_RESPONSES)
            runner = FakeRunner(responses)
            with unittest.mock.patch.object(capability_probe.subprocess, "run", runner):
                snapshot = capability_probe.buildSnapshot(Path(tmp), ["repository", "ci"], timeout=5.0)
        self.assertEqual(sorted(snapshot["sections"]), ["ci", "repository"])

    def test_section_builder_crash_degrades_to_unknown_field(self):
        def explode():
            raise RuntimeError("boom")

        section = capability_probe.safeSection(explode, "repository")
        self.assertEqual(section["probeError"]["status"], "unknown")
        self.assertIn("RuntimeError", section["probeError"]["evidence"])


class CliTest(unittest.TestCase):
    def test_json_cli_exits_zero_even_with_missing_capabilities(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch.object(capability_probe.shutil, "which", lambda name: None):
                with unittest.mock.patch.object(
                    capability_probe.subprocess, "run", FakeRunner({}, default=FileNotFoundError("tool"))
                ):
                    with unittest.mock.patch.object(capability_probe, "resolveExecutable", lambda name: None):
                        with contextlib.redirect_stdout(stdout):
                            exitCode = capability_probe.main(["--json", "--repo-root", tmp])
        self.assertEqual(exitCode, 0)
        snapshot = json.loads(stdout.getvalue())
        self.assertEqual(sorted(snapshot["sections"]), list(capability_probe.SECTION_NAMES))

    def test_usage_error_exits_non_zero(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as context:
                capability_probe.main(["--section", "bogus"])
        self.assertEqual(context.exception.code, 2)


class RedactionTest(unittest.TestCase):
    def test_redaction_covers_token_shapes_and_truncates(self):
        text = f"Authorization: Bearer abc.def token={FAKE_TOKEN} https://user:{FAKE_URL_PASSWORD}@github.com " + (
            "x" * 500
        )
        redacted = capability_probe.redactText(text)
        self.assertNotIn(FAKE_TOKEN, redacted)
        self.assertNotIn(FAKE_URL_PASSWORD, redacted)
        self.assertNotIn("Bearer abc.def", redacted)
        self.assertLessEqual(len(redacted), capability_probe.MAX_EVIDENCE_CHARS)


if __name__ == "__main__":
    unittest.main()
