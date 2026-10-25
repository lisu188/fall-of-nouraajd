"""Registration-report source tests; no game module, config inventory or native runtime needed."""

import ast
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def selectedRunnerFunction(source, name):
    match = re.search(r"(?m)^def " + re.escape(name) + r"\(", source)
    if match is None:
        raise AssertionError("Missing runner helper: " + name)
    following = re.search(r"(?m)^(?:def |class |@)", source[match.end() :])
    if following is None:
        raise AssertionError("Missing helper boundary: " + name)
    node = ast.parse(source[match.start() : match.end() + following.start()]).body[0]
    if not isinstance(node, ast.FunctionDef) or node.name != name:
        raise AssertionError("Invalid helper boundary: " + name)
    return node


class BuiltinGameplayRegistrationTest(unittest.TestCase):
    def runnerFunctions(self, source_root=None):
        source = (ROOT / "test.py").read_text(encoding="utf-8")
        names = ("load_registered_class_categories", "runtime_type_details")
        namespace = {"REPO_ROOT": ROOT if source_root is None else source_root, "re": re}
        selected = ast.Module(body=[selectedRunnerFunction(source, name) for name in names], type_ignores=[])
        exec(compile(ast.fix_missing_locations(selected), "<selected registration helpers>", "exec"), namespace)
        return namespace

    def testActualGameplayTableRowsHaveBuiltinSourceOwnership(self):
        categories = self.runnerFunctions()["load_registered_class_categories"]()
        table = (ROOT / "src/core/CGameplayTypeTable.h").read_text(encoding="utf-8")
        rows = re.findall(r"(?m)^\s+FN_(?:TYPE|WRAPPED)\((C[A-Za-z0-9_]+),", table)
        self.assertGreaterEqual(len(rows), 30)
        self.assertIn("CItem", rows)
        self.assertIn("CEffect", rows)
        for class_name in rows:
            with self.subTest(class_name=class_name):
                self.assertEqual(
                    {
                        "category": "gameplay-registration",
                        "owner": "src/core/CGameplayTypeTable.h",
                        "className": class_name,
                    },
                    categories.get(class_name),
                )

    def testCoreOwnershipAndRuntimeReportPrecedenceStayIntact(self):
        helpers = self.runnerFunctions()
        categories = helpers["load_registered_class_categories"]()
        self.assertEqual(
            {"category": "core-registration", "owner": "src/core/CCoreTypeRegistration.cpp", "className": "CGame"},
            categories.get("CGame"),
        )
        details = helpers["runtime_type_details"]
        configured = {"CItem": {"category": "configured", "owner": "selected/config.json", "className": "CWeapon"}}
        self.assertEqual({**configured["CItem"], "typeId": "CItem"}, details("CItem", configured, categories))
        self.assertNotIn("typeId", configured["CItem"])
        self.assertEqual({**categories["CGame"], "typeId": "CGame"}, details("CGame", {}, categories))
        self.assertEqual(
            {
                "category": "runtime-registration",
                "owner": "CObjectHandler.registerType",
                "className": "",
                "typeId": "customFactory",
            },
            details("customFactory", {}, categories),
        )

    def testMacroParametersAndWrapperImplementationNamesAreNotConcreteTypes(self):
        categories = self.runnerFunctions()["load_registered_class_categories"]()
        for name in ("T", "FN_TYPE", "FN_WRAPPED", "CWrapper<CEffect>"):
            self.assertNotIn(name, categories)
        self.assertTrue(all(re.fullmatch(r"C[A-Za-z0-9_]+", name) for name in categories))

    def testExistingCategoriesAndFirstOwnerWinAgainstNonRowDecoys(self):
        with tempfile.TemporaryDirectory(prefix="nouraajd-registration-source-") as directory:
            root = Path(directory)
            sources = {
                "src/core/CCoreTypeRegistration.cpp": ("core-registration", "CGame"),
                "src/handler/CHandlerTypeRegistration.cpp": ("handler-registration", "CHandlerExample"),
                "src/object/CObjectTypeRegistration.cpp": ("object-registration", "CObjectExample"),
                "src/gui/CGuiTypeRegistration.cpp": ("gui-registration", "CGuiExample"),
                "src/gui/CAnimationTypeRegistration.cpp": ("animation-registration", "CAnimationExample"),
                "src/gui/object/CGuiWidgetTypeRegistration.cpp": ("widget-registration", "CWidgetExample"),
                "src/gui/panel/CGuiPanelTypeRegistration.cpp": ("panel-registration", "CPanelExample"),
            }
            for relative, (_, class_name) in sources.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("CTypes::register_type<" + class_name + ", CGameObject>();\n", encoding="utf-8")
            table = root / "src/core/CGameplayTypeTable.h"
            table.write_text(
                "#define FN_GAMEPLAY_TYPES(FN_TYPE, FN_WRAPPED)\n"
                "    FN_TYPE(CItem, CGameObject)\n"
                "    FN_WRAPPED(CEffect, CGameObject)\n"
                "    FN_TYPE(CGame, CGameObject)\n"
                "    FN_TYPE(T, CGameObject)\n"
                "    FN_WRAPPED(CWrapper<CEffect>, CGameObject)\n"
                "// FN_TYPE(CCommentOnly, CGameObject)\n",
                encoding="utf-8",
            )
            legacy = root / "src/plugin/NativePlugin.cpp"
            legacy.parent.mkdir(parents=True)
            legacy.write_text("CTypes::register_type<CObsoletePlugin>();\n", encoding="utf-8")
            categories = self.runnerFunctions(root)["load_registered_class_categories"]()
            for relative, (category, class_name) in sources.items():
                self.assertEqual(
                    {"category": category, "owner": relative, "className": class_name}, categories[class_name]
                )
            self.assertEqual("gameplay-registration", categories.get("CItem", {}).get("category"))
            self.assertEqual("gameplay-registration", categories.get("CEffect", {}).get("category"))
            for name in ("T", "FN_TYPE", "FN_WRAPPED", "CWrapper<CEffect>", "CCommentOnly", "CObsoletePlugin"):
                self.assertNotIn(name, categories)


if __name__ == "__main__":
    unittest.main()
