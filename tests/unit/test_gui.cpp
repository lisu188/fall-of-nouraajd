/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026  Andrzej Lis

This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

#include "core/CGame.h"
#include "core/CMap.h"
#include "core/CStats.h"
#include "gui/CGui.h"
#include "gui/object/CWidget.h"
#include "gui/panel/CGameInventoryPanel.h"
#include "object/CItem.h"
#include "object/CPlayer.h"
#include "test_harness.h"

#include <pybind11/embed.h>

namespace {

void test_widget_ignores_unarmed_non_left_clicks() {
    auto widget = std::make_shared<CWidget>();

    expect_true(!widget->mouseEvent(nullptr, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_RIGHT, 0, 0),
                "plain widget should ignore right clicks when no click callback is armed");
}

std::shared_ptr<CStats> player_stats() {
    auto stats = std::make_shared<CStats>();
    stats->setMainStat("stamina");
    stats->setStamina(10);
    return stats;
}

void test_inventory_double_select_uses_selected_item_and_clears_selection() {
    SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    auto game = std::make_shared<CGame>();
    auto map = std::make_shared<CMap>();
    auto gui = std::make_shared<CGui>();
    auto player = std::make_shared<CPlayer>();
    auto potion = std::make_shared<CPotion>();
    auto panel = std::make_shared<CGameInventoryPanel>();

    game->setMap(map);
    game->setGui(gui);
    map->setGame(game);
    gui->setGame(game);

    player->setGame(game);
    player->setBaseStats(player_stats());
    player->setHp(player->getHpMax());
    map->setPlayer(player);

    potion->setGame(game);
    potion->setName("coveredFullHealthPotion");
    potion->addTag(CTag::Heal);
    player->addItem(potion);

    const auto inventory_size = player->getItems().size();
    panel->inventoryCallback(gui, 0, potion);
    expect_true(panel->inventorySelect(gui, 0, potion), "first inventory click should select a usable item");

    panel->inventoryCallback(gui, 0, potion);
    expect_true(player->getItems().size() == inventory_size,
                "full-health potion double-select should call useItem without consuming the item");
    expect_true(!panel->inventorySelect(gui, 0, potion), "second inventory click should clear the used selection");
}

} // namespace

int main() {
    pybind11::scoped_interpreter guard{};

    test_widget_ignores_unarmed_non_left_clicks();
    test_inventory_double_select_uses_selected_item_and_clears_selection();

    return finish_tests();
}
