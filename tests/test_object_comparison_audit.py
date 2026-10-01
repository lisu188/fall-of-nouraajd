import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "object-comparison-semantics.md"


class ObjectComparisonAuditTest(unittest.TestCase):
    def read(self, relative_path):
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_audit_document_covers_required_semantic_categories(self):
        doc = DOC.read_text(encoding="utf-8")
        for phrase in (
            "Shared-pointer identity",
            "Runtime map/object identity",
            "Configured type equality",
            "Serialized value equality",
        ):
            self.assertIn(phrase, doc)
        for source_path in (
            "src/object/CGameObject.cpp",
            "src/object/CCreature.cpp",
            "src/object/CMarket.cpp",
            "src/object/CPlayer.cpp",
            "src/object/CDialog.cpp",
            "src/object/CMapObject.cpp",
            "src/handler/CEventHandler.cpp",
            "src/handler/CFightHandler.cpp",
            "src/handler/CRngHandler.cpp",
            "src/handler/CGuiHandler.cpp",
            "src/gui/object/CGameGraphicsObject.cpp",
            "src/gui/object/CProxyGraphicsObject.cpp",
            "src/gui/panel/CListView.cpp",
            "src/gui/panel/CGameInventoryPanel.cpp",
            "src/gui/panel/CGameTradePanel.cpp",
            "src/gui/panel/CGameFightPanel.cpp",
            "src/gui/panel/CGameDialogPanel.cpp",
            "src/gui/panel/CGameLootPanel.cpp",
        ):
            self.assertIn(source_path, doc)

    def test_source_patterns_match_documented_current_semantics(self):
        game_object = self.read("src/object/CGameObject.cpp")
        self.assertIn("return CGameObject::sameConfiguredType(a, b);", game_object)
        self.assertRegex(
            game_object,
            re.compile(
                r"sameConfiguredType.*?getTypeId\(\) == b->getTypeId\(\).*?"
                r"getType\(\) == b->getType\(\) && a->getName\(\) == b->getName\(\)",
                re.S,
            ),
        )

        creature = self.read("src/object/CCreature.cpp")
        self.assertIn("vstd::ctn(effects, effect, CGameObject::sameConfiguredType)", creature)
        self.assertIn("CGameObject::sameInstance((*it).second, item)", creature)
        self.assertIn("CGameObject::sameRuntimeIdentity(map->getObjectByName(self->getName()), self)", creature)
        self.assertIn("std::set<std::shared_ptr<CItem>> allItems", creature)

        graphics = self.read("src/gui/object/CGameGraphicsObject.cpp")
        self.assertIn("children.insert(child)", graphics)
        self.assertIn("children.erase(child)", graphics)
        self.assertIn("return a < b;", graphics)

        fight = self.read("src/handler/CFightHandler.cpp")
        self.assertIn("std::unordered_set<const CCreature *> identities", fight)
        self.assertIn("std::find(participants.begin(), participants.end(), creature)", fight)
        self.assertIn("map->getObjectByName(creature->getName()) == creature", fight)

        events = self.read("src/handler/CEventHandler.cpp")
        self.assertIn("CGameObject::sameInstance(existing, trigger)", events)
        self.assertIn("CGameObject::sameConfiguredType(existing, trigger)", events)

        fight_panel = self.read("src/gui/panel/CGameFightPanel.cpp")
        self.assertIn("names.insert(candidate->getName()).second", fight_panel)
        self.assertIn("CGameObject::sameInstance(enemy.lock(), object)", fight_panel)

        inventory_panel = self.read("src/gui/panel/CGameInventoryPanel.cpp")
        self.assertIn("CGameObject::sameInstance(selectedInventory.lock(), object)", inventory_panel)
        self.assertIn("CGameObject::sameInstance(selectedEquipped.lock(), object)", inventory_panel)

        trade_panel = self.read("src/gui/panel/CGameTradePanel.cpp")
        self.assertIn("CGameObject::sameInstance(selection.lock(), object)", trade_panel)


if __name__ == "__main__":
    unittest.main()
