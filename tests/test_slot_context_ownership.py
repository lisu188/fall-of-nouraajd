from pathlib import Path
import re
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]


def readSource(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


class SlotContextOwnershipTest(unittest.TestCase):
    def test_slot_configuration_lazy_owner_lives_on_game_context(self) -> None:
        context_header = readSource("src/core/CGameContext.h")

        self.assertIn("class CSlotConfig;", context_header)
        self.assertIn("std::shared_ptr<CSlotConfig> getSlotConfiguration();", context_header)
        self.assertIn("vstd::lazy<CSlotConfig> slotConfiguration;", context_header)

    def test_game_keeps_slot_configuration_facade_without_lazy_owner(self) -> None:
        game_header = readSource("src/core/CGame.h")
        game_source = readSource("src/core/CGame.cpp")

        self.assertIn("class CSlotConfig;", game_header)
        self.assertIn("std::shared_ptr<CSlotConfig> getSlotConfiguration();", game_header)
        self.assertNotIn("vstd::lazy<CSlotConfig> slotConfiguration;", game_header)
        self.assertRegex(
            game_source,
            re.compile(
                r"std::shared_ptr<CSlotConfig>\s+CGame::getSlotConfiguration\(\)\s*\{\s*"
                r"return\s+getContext\(\)->getSlotConfiguration\(\);\s*\}"
            ),
        )

    def test_context_creates_slot_configuration_through_owner_game(self) -> None:
        context_source = readSource("src/core/CGameContext.cpp")

        self.assertIn('throw std::runtime_error("Cannot create CSlotConfig without an active CGame.");', context_source)
        self.assertIn('owner->createObject<CSlotConfig>("slotConfiguration")', context_source)

    def test_inventory_and_equipment_call_existing_game_facade(self) -> None:
        creature_source = readSource("src/object/CCreature.cpp")
        inventory_panel_source = readSource("src/gui/panel/CGameInventoryPanel.cpp")

        self.assertIn("getMap()->getGame()->getSlotConfiguration()->canFit", creature_source)
        self.assertGreaterEqual(inventory_panel_source.count("gui->getGame()->getSlotConfiguration()"), 3)


if __name__ == "__main__":
    unittest.main()
