# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import ast
import hashlib
import json
from pathlib import Path
import re
import unittest

from tests.cpp_bindings import (
    BINDING_GROUPS,
    bindingSourcePaths,
    readBindingSources,
    registrationBody,
    registrationTokens,
)

ROOT = Path(__file__).resolve().parents[1]


class BindingSourceLayoutTest(unittest.TestCase):
    def testCityRunnerImportsUseExportedClassesAndMatchingFastPrefixes(self):
        runner = ast.parse((ROOT / "test.py").read_text(encoding="utf-8"))
        imports = [
            node
            for node in ast.walk(runner)
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("tests.test_baldurs_gate_city_")
        ]
        self.assertTrue(imports, "City source tests must remain registered in the runner")
        wrappers = {node.name: node for node in ast.walk(runner) if isinstance(node, ast.ClassDef)}
        prefixes = next(
            ast.literal_eval(node.value)
            for node in runner.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "FAST_TEST_PREFIXES" for target in node.targets)
        )
        deleted = {
            name.id
            for node in ast.walk(runner)
            if isinstance(node, ast.Delete)
            for target in node.targets
            for name in ast.walk(target)
            if isinstance(name, ast.Name)
        }
        for node in imports:
            module = ast.parse((ROOT / (node.module.replace(".", "/") + ".py")).read_text(encoding="utf-8"))
            exports = {item.name for item in module.body if isinstance(item, ast.ClassDef)}
            for imported in node.names:
                with self.subTest(module=node.module, imported=imported.name):
                    self.assertIn(imported.name, exports)
                    self.assertEqual("_" + imported.name, imported.asname)
                    self.assertIn(imported.name, wrappers)
                    self.assertEqual(
                        [imported.asname],
                        [base.id for base in wrappers[imported.name].bases if isinstance(base, ast.Name)],
                    )
                    self.assertIn(imported.name + ".", prefixes)
                    self.assertIn(imported.asname, deleted)

    def testRegistrationContractPreservesSignaturesDefaultsAliasesAndOrder(self):
        # This is a reviewed compatibility fixture, not a generated expected value from the implementation.
        # Intentional binding API changes must update the fixture alongside their runtime contract tests.
        fixture = json.loads((ROOT / "tests/fixtures/python_binding_contract.json").read_text(encoding="utf-8"))
        self.assertEqual(
            list(BINDING_GROUPS), [(Path(group["source"]).name, group["registration"]) for group in fixture["groups"]]
        )
        for group in fixture["groups"]:
            with self.subTest(source=group["source"]):
                source = (ROOT / group["source"]).read_text(encoding="utf-8")
                body = registrationBody(source, group["registration"])
                digest = hashlib.sha256(registrationTokens(body).encode()).hexdigest()
                self.assertEqual(group["registrationTokenSha256"], digest)

    def testAlliedCombatBindingsConvertAllThreeParticipantsWithoutChangingLegacyCalls(self):
        source = (ROOT / "src/core/bindings/CModuleServices.cpp").read_text(encoding="utf-8")
        for name, native_name in (
            ("fightManyWithAllies", "fightManyWithAllies"),
            ("fightManyWithAlliesOutcome", "fightManyWithAlliesOutcome"),
        ):
            match = re.search(
                r'"' + name + r'",\s*\[\]\(std::shared_ptr<CCreature> hero, '
                r"const py::iterable &opponents, const py::iterable &allies\)\s*\{(.*?)\}",
                source,
                re.DOTALL,
            )
            self.assertIsNotNone(match, name)
            self.assertIn("CFightHandler::" + native_name + "(hero, creature_iterable_to_vector(opponents),", match[1])
            self.assertIn("creature_iterable_to_vector(allies)", match[1])
        self.assertIn('"fightManyOutcome"', source)
        self.assertNotIn('"fightManyWithAlliesAsync"', source)

    def testCoordinatorRegistersEachGroupOnceAfterMetadataInOriginalOrder(self):
        source = (ROOT / "src/core/CModule.cpp").read_text(encoding="utf-8")
        body = registrationBody(source, "init_game_module")
        self.assertEqual([name for _, name in BINDING_GROUPS], re.findall(r"\b(bind\w+)\(m(?:,|\))", body))
        self.assertLess(body.index("register_python_binding_type_metadata();"), body.index(BINDING_GROUPS[0][1]))
        self.assertEqual(1, body.count("std::make_shared<CPythonEventCallbacks>()"))
        self.assertEqual(1, body.count('py::module_::import("atexit")'))
        self.assertIn("bindFoundationAndSession(m, pythonEventCallbacks);", body)
        self.assertIn("bindServices(m, pythonEventCallbacks);", body)
        self.assertIn("CTypes::register_type_metadata<CStats, CGameObject>();", source)
        self.assertIn("CTypes::register_type_metadata<CDamage, CGameObject>();", source)
        self.assertIn("FN_GAMEPLAY_TYPES(FN_TYPE, FN_WRAPPED)", source)
        self.assertIn("FN_GAMEPLAY_TYPES(FN_IGNORE, FN_DOWNCAST)", source)

    def testOpaqueCasterIsSharedBeforeEveryBindingAndEntryLivesOnlyInShim(self):
        header = (ROOT / "src/core/bindings/CModuleBindings.h").read_text(encoding="utf-8")
        opaque = "PYBIND11_MAKE_OPAQUE(std::vector<std::string>);"
        self.assertEqual(1, header.count(opaque))
        self.assertNotIn("PYBIND11_MAKE_OPAQUE", readBindingSources(ROOT))
        for path in bindingSourcePaths(ROOT):
            source = path.read_text(encoding="utf-8")
            includes = re.findall(r"^#include\s+([^\n]+)", source, re.MULTILINE)
            self.assertTrue(includes[0].endswith('CModuleBindings.h"'), path.name)
            self.assertNotIn("PYBIND11_MODULE", source)
        entry = (ROOT / "src/core/CModuleEntry.cpp").read_text(encoding="utf-8")
        self.assertEqual(1, entry.count("PYBIND11_MODULE(_game, m)"))
        self.assertIn("init_game_module(m);", entry)


if __name__ == "__main__":
    unittest.main()
