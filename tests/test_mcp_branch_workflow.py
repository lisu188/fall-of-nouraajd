# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Diagnostic shard scheduling cannot turn failed parent validation into acceptance."""

import ast
import os
from pathlib import Path
import re
import textwrap
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def workflowJob(name):
    workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
    start = workflow.index("\n  " + name + ":\n") + 1
    next_job = re.search(r"\n  [a-zA-Z0-9-]+:\n", workflow[start + 1 :])
    end = start + 1 + next_job.start() if next_job else len(workflow)
    return workflow[start:end]


def workflowScalar(source, name, indentation):
    match = re.search(r"(?m)^" + " " * indentation + re.escape(name) + r":\s*(.*)$", source)
    if match is None:
        return ""
    value = match.group(1)
    if value not in {">-", ">", "|", "|-"}:
        return value
    following = []
    for line in source[match.end() :].splitlines():
        if not line.strip():
            continue
        if not line.startswith(" " * (indentation + 2)):
            break
        following.append(line)
    result = textwrap.dedent("\n".join(following))
    return " ".join(result.splitlines()) if value.startswith(">") else result


def workflowStep(job, name):
    marker = "      - name: " + name + "\n"
    body = job.split(marker, 1)[1]
    return marker + body.split("\n      - ", 1)[0]


def evaluateCondition(expression, facts, *, prior_success=True, cancelled=False):
    """Evaluate the workflow's small boolean subset, including Actions' default success guard."""
    expression = expression.strip()
    if expression.startswith("${{") and expression.endswith("}}"):
        expression = expression[3:-2].strip()
    has_status = bool(re.search(r"\b(?:always|cancelled|success|failure)\s*\(", expression))
    if not has_status and not prior_success:
        return False
    if not expression:
        return True
    expression = re.sub(
        r"\b(?:needs|steps)\.[a-zA-Z0-9-]+\.(?:outputs\.[a-zA-Z0-9-]+|result|outcome)\b",
        lambda match: repr(facts.get(match.group(), "")),
        expression,
    )
    for name, value in (("always", True), ("cancelled", cancelled), ("success", prior_success)):
        expression = expression.replace(name + "()", repr(value))
    expression = expression.replace("&&", " and ").replace("||", " or ")
    expression = re.sub(r"!(?!=)", " not ", expression).strip()
    tree = ast.parse(expression, mode="eval")
    allowed = (
        ast.Expression,
        ast.BoolOp,
        ast.UnaryOp,
        ast.Compare,
        ast.Constant,
        ast.And,
        ast.Or,
        ast.Not,
        ast.Eq,
        ast.NotEq,
    )
    if any(not isinstance(node, allowed) for node in ast.walk(tree)):
        raise AssertionError("Unsupported workflow condition; extend the reviewed test evaluator: " + expression)
    return bool(eval(compile(tree, "<workflow condition>", "eval"), {"__builtins__": {}}))


class McpBranchWorkflowTest(unittest.TestCase):
    def facts(self, platform):
        return {
            "needs.linux-fast.result": "success",
            "needs.linux-fast.outputs.native-needed": "true",
            "needs." + platform + ".result": "success",
            "needs." + platform + ".outputs.runtime-ready": "true",
        }

    def aggregateProgram(self):
        aggregate = workflowJob("mcp-branches")
        final = workflowStep(aggregate, "Require the complete branch matrix on both platforms")
        script = workflowScalar(final, "run", 8)
        self.assertTrue(script.startswith("python3 - <<'PY'\n"))
        self.assertTrue(script.endswith("\nPY"))
        return compile(script.split("\n", 1)[1].rsplit("\nPY", 1)[0], "<actual branch aggregate gate>", "exec")

    def aggregateEnvironment(self):
        final = workflowStep(workflowJob("mcp-branches"), "Require the complete branch matrix on both platforms")
        environment = {
            match.group(1): "success"
            for match in re.finditer(r"(?m)^          ([A-Z_]+): \$\{\{ needs\.[a-zA-Z0-9-]+\.result \}\}$", final)
        }
        environment["COVERAGE_NEEDED"] = "true"
        return environment

    def runAggregate(self, environment):
        with patch.dict(os.environ, environment, clear=True):
            exec(self.aggregateProgram(), {"__name__": "__main__"})

    def testRuntimeReadinessComesOnlyFromTheActualSuccessfulPinnedUpload(self):
        for platform in ("linux", "windows"):
            with self.subTest(platform=platform):
                job = workflowJob(platform)
                output = workflowScalar(job, "runtime-ready", 6)
                upload = workflowStep(job, "Upload current " + platform.title() + " MCP runtime")
                self.assertEqual("mcp-runtime-upload", workflowScalar(upload, "id", 8))
                self.assertIn("actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a", upload)
                self.assertEqual("error", workflowScalar(upload, "if-no-files-found", 10))
                self.assertNotIn("continue-on-error:", upload)
                for outcome in ("", "skipped", "failure", "cancelled", "success"):
                    self.assertIs(
                        outcome == "success",
                        evaluateCondition(output, {"steps.mcp-runtime-upload.outcome": outcome}),
                    )
                self.assertFalse(
                    evaluateCondition(
                        workflowScalar(upload, "if", 8),
                        {"needs.linux-fast.outputs.native-needed": "true"},
                        prior_success=False,
                    ),
                    "A failed native build/import/bundle cannot bypass the upload's default success guard",
                )

    def testSuccessfulUploadAllowsDiagnosticShardsAfterLaterParentGameplayFailure(self):
        for platform in ("linux", "windows"):
            with self.subTest(platform=platform):
                condition = workflowScalar(workflowJob("mcp-branches-" + platform), "if", 4)
                facts = self.facts(platform)
                facts["needs." + platform + ".result"] = "failure"
                self.assertTrue(evaluateCondition(condition, facts, prior_success=False))
                with self.assertRaises(SystemExit):
                    self.runAggregate({**self.aggregateEnvironment(), platform.upper() + "_RESULT": "failure"})

    def testMissingArtifactFastFailureNonNativeSelectionAndCancellationPreventShards(self):
        for platform in ("linux", "windows"):
            condition = workflowScalar(workflowJob("mcp-branches-" + platform), "if", 4)
            for defect in ("missing-upload", "failed-upload", "failed-fast", "skipped-fast", "non-native", "cancelled"):
                with self.subTest(platform=platform, defect=defect):
                    facts = self.facts(platform)
                    if defect.endswith("upload"):
                        output = workflowScalar(workflowJob(platform), "runtime-ready", 6)
                        uploaded = evaluateCondition(
                            output, {"steps.mcp-runtime-upload.outcome": "failure" if defect == "failed-upload" else ""}
                        )
                        facts["needs." + platform + ".outputs.runtime-ready"] = str(uploaded).lower()
                    elif defect.endswith("fast"):
                        facts["needs.linux-fast.result"] = "failure" if defect == "failed-fast" else "skipped"
                    elif defect == "non-native":
                        facts["needs.linux-fast.outputs.native-needed"] = "false"
                    scheduled = evaluateCondition(condition, facts, cancelled=defect == "cancelled")
                    self.assertFalse(scheduled)
                    with self.assertRaises(SystemExit):
                        self.runAggregate(
                            {
                                **self.aggregateEnvironment(),
                                platform.upper() + "_BRANCH_RESULT": "success" if scheduled else "skipped",
                            }
                        )

    def testAggregateDirectlyObservesEveryNativeFullCoverageAndMatrixConclusion(self):
        aggregate = workflowJob("mcp-branches")
        needs = set(re.findall(r"(?m)^      - ([a-zA-Z0-9-]+)$", aggregate.split("    if:", 1)[0]))
        self.assertEqual(
            {
                "linux-fast",
                "linux",
                "windows-deps",
                "windows",
                "linux-coverage",
                "mcp-branches-linux",
                "mcp-branches-windows",
            },
            needs,
        )
        self.assertEqual("always()", workflowScalar(aggregate, "if", 4))
        environment = self.aggregateEnvironment()
        self.assertEqual(
            {
                "LINUX_FAST_RESULT",
                "LINUX_RESULT",
                "WINDOWS_DEPS_RESULT",
                "WINDOWS_RESULT",
                "COVERAGE_RESULT",
                "COVERAGE_NEEDED",
                "LINUX_BRANCH_RESULT",
                "WINDOWS_BRANCH_RESULT",
            },
            set(environment),
        )
        self.runAggregate(environment)
        for name in set(environment) - {"COVERAGE_NEEDED"}:
            for outcome in ("failure", "cancelled", "skipped", ""):
                with self.subTest(job=name, outcome=outcome):
                    with self.assertRaises(SystemExit):
                        self.runAggregate({**environment, name: outcome})

    def testOptionalCoverageMayOnlySucceedOrBeSkippedAndRequiredCoverageCannotBeSkipped(self):
        environment = {**self.aggregateEnvironment(), "COVERAGE_NEEDED": "false"}
        for outcome in ("success", "skipped"):
            self.runAggregate({**environment, "COVERAGE_RESULT": outcome})
        for outcome in ("failure", "cancelled", ""):
            with self.subTest(outcome=outcome), self.assertRaises(SystemExit):
                self.runAggregate({**environment, "COVERAGE_RESULT": outcome})
        with self.assertRaises(SystemExit):
            self.runAggregate({**environment, "COVERAGE_NEEDED": "true", "COVERAGE_RESULT": "skipped"})

    def testRuntimeTransferAndReceiptAuditsKeepTheCheckoutShaAndPendingGate(self):
        for platform in ("linux", "windows"):
            job = workflowJob("mcp-branches-" + platform)
            self.assertIn("name: mcp-branch-runtime-" + platform + "-${{ github.sha }}", job)
            self.assertIn('--head "${{ github.sha }}"', job)
            self.assertIn("GAME_MCP_BRANCH_HEAD: ${{ github.sha }}", job)
        aggregate = workflowJob("mcp-branches")
        for platform in ("Linux", "Windows"):
            audit = workflowStep(aggregate, "Require exact " + platform + " receipts and collect measured timings")
            self.assertEqual("always()", workflowScalar(audit, "if", 8))
            self.assertNotIn("continue-on-error:", audit)
            self.assertIn("audit-receipts --platform " + platform.lower(), audit)
            self.assertIn('--head "${{ github.sha }}"', audit)


if __name__ == "__main__":
    unittest.main()
