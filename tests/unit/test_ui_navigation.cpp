/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026 Andrzej Lis
SPDX-License-Identifier: GPL-3.0-or-later
*/
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CJsonUtil.h"
#include "core/CController.h"
#include "core/CMap.h"
#include "core/CStats.h"
#include "core/CTypeRegistration.h"
#include "core/CTypes.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/CTextManager.h"
#include "gui/object/CMapGraphicsObject.h"
#include "gui/object/CWidget.h"
#include "gui/panel/CGameInventoryPanel.h"
#include "gui/panel/CGameQuestPanel.h"
#include "handler/CObjectHandler.h"
#include "object/CItem.h"
#include "object/CPlayer.h"
#include "object/CTile.h"
#include "object/CQuest.h"
#include "test_harness.h"

#include <pybind11/embed.h>
#include <cstdio>
#include <set>

namespace {
std::shared_ptr<CLayout> fixedLayout(int x, int y, int width, int height) {
    auto layout = std::make_shared<CLayout>();
    layout->setRect(x, y, width, height);
    return layout;
}

bool keyEvent(const std::shared_ptr<CGui> &gui, SDL_Keycode key, SDL_EventType type = SDL_KEYDOWN) {
    SDL_Event event{};
    event.type = type;
    event.key.keysym.sym = key;
    return gui->event(&event);
}

void mouseEvent(const std::shared_ptr<CGui> &gui, SDL_EventType type, int x, int y) {
    SDL_Event event{};
    event.type = type;
    event.button.button = SDL_BUTTON_LEFT;
    event.button.x = x;
    event.button.y = y;
    gui->event(&event);
}

void clickWidget(const std::shared_ptr<CGui> &gui, const std::shared_ptr<CGameGraphicsObject> &widget) {
    auto rect = widget->getLayout()->getRect(widget);
    mouseEvent(gui, SDL_MOUSEBUTTONDOWN, rect->x + rect->w / 2, rect->y + rect->h / 2);
    mouseEvent(gui, SDL_MOUSEBUTTONUP, rect->x + rect->w / 2, rect->y + rect->h / 2);
}

std::shared_ptr<CWidget> findAction(const std::shared_ptr<CGameGraphicsObject> &root, const std::string &action) {
    if (auto widget = vstd::cast<CWidget>(root); widget && widget->getClick() == action)
        return widget;
    for (const auto &child : root->getChildren()) {
        if (auto found = findAction(child, action))
            return found;
    }
    return nullptr;
}

struct NavigationHarness {
    std::shared_ptr<CGame> game = std::make_shared<CGame>();
    std::shared_ptr<CMap> map = std::make_shared<CMap>();
    std::shared_ptr<CGui> gui = std::make_shared<CGui>();
    std::shared_ptr<CPlayer> player = std::make_shared<CPlayer>();

    NavigationHarness() {
        for (const auto &[name, builder] : *CTypes::builders())
            game->getObjectHandler()->registerType(name, builder);
        game->getObjectHandler()->registerConfig("slotConfiguration", CJsonUtil::from_string(R"({
            "class": "CSlotConfig", "properties": {"configuration": {
                "0": {"class": "CSlot", "properties": {"slotName": "RightHand", "types": ["CWeapon"]}}
            }}})",
                                                                                             "slotConfiguration"));
        game->setMap(map);
        game->setGui(gui);
        map->setGame(game);
        gui->setGame(game);
        gui->setLayout(fixedLayout(0, 0, 1280, 900));
        map->setXBounds({{0, 12}});
        map->setYBounds({{0, 8}});
        for (int x = 0; x < 12; ++x) {
            for (int y = 0; y < 8; ++y) {
                auto tile = std::make_shared<CTile>();
                tile->setGame(game);
                tile->setCanStep(true);
                map->addTile(tile, x, y, 0);
            }
        }
        player->setGame(game);
        auto stats = std::make_shared<CStats>();
        stats->setMainStat("stamina");
        stats->setStamina(10);
        player->setBaseStats(stats);
        map->setPlayer(player);
        auto controller = std::make_shared<CPlayerController>();
        controller->setGame(game);
        player->setController(controller);
    }

    ~NavigationHarness() { game->getContext()->shutdown(); }

    std::shared_ptr<CItem> item(const std::string &label) {
        auto item = std::make_shared<CItem>();
        item->setGame(game);
        item->setName(label);
        item->setTypeId(label);
        item->setLabel(label);
        player->addItem(item);
        return item;
    }

    std::shared_ptr<CGameInventoryPanel> panel() {
        auto panel = std::make_shared<CGameInventoryPanel>();
        panel->setGame(game);
        panel->setTypeId("inventoryPanel");
        panel->setModal(true);
        panel->setLayout(fixedLayout(100, 80, 900, 720));
        gui->pushChild(panel);
        return panel;
    }

    std::shared_ptr<CListView> list(const std::shared_ptr<CGameInventoryPanel> &panel, bool searchable) {
        auto list = std::make_shared<CListView>();
        list->setGame(game);
        list->setRows(true);
        list->setSearchable(searchable);
        list->setDragEnabled(false);
        list->setShowEmpty(false);
        list->setTileSize(64);
        list->setCollection("inventoryCollection");
        list->setCallback("inventoryCallback");
        list->setSelect("inventorySelect");
        list->setLayout(fixedLayout(40, 120, 500, 256));
        panel->addChild(list);
        list->initialize();
        vstd::event_loop<>::instance()->run();
        list->refresh();
        return list;
    }
};

std::set<std::string> visibleRowLabels(const NavigationHarness &h, const std::shared_ptr<CListView> &list);

void testSearchTextDoesNotTriggerPanelHotkeys() {
    NavigationHarness h;
    auto iron = h.item("Iron blade");
    h.item("Wooden staff");
    auto panel = h.panel();
    auto list = h.list(panel, true);
    h.gui->focusWidget(list);
    keyEvent(h.gui, SDLK_SLASH);
    for (char letter : std::string("iron")) {
        keyEvent(h.gui, static_cast<SDL_Keycode>(letter));
        SDL_Event event{};
        event.type = SDL_TEXTINPUT;
        event.text.text[0] = letter;
        event.text.text[1] = '\0';
        h.gui->event(&event);
        keyEvent(h.gui, static_cast<SDL_Keycode>(letter), SDL_KEYUP);
    }
    expect_true(panel->isAttachedToGui(h.gui), "typing inventory's I shortcut into search must not close its panel");
    expect_true(visibleRowLabels(h, list) == std::set<std::string>{"Iron blade"},
                "typed search must filter to the matching item");
    keyEvent(h.gui, SDLK_RETURN);
    expect_true(panel->inventorySelect(h.gui, 0, iron), "Enter on a filtered row must inspect the matching item");
    expect_true(h.player->hasInInventory(iron), "search navigation must not consume or equip the selected item");
}

std::set<std::string> visibleRowLabels(const NavigationHarness &h, const std::shared_ptr<CListView> &list) {
    std::set<std::string> labels;
    for (int y = 0; y < list->getSizeY(h.gui); ++y) {
        for (const auto &graphic : list->getProxiedObjects(h.gui, 0, y)) {
            if (auto text = vstd::cast<CTextWidget>(graphic); text && !text->getText().empty())
                labels.insert(text->getText());
        }
    }
    return labels;
}

void testRowPagingHasWorkingPreviousAndNextControls() {
    NavigationHarness h;
    std::set<std::string> expected;
    for (int i = 0; i < 11; ++i) {
        auto label = "Relic " + std::to_string(i);
        expected.insert(label);
        h.item(label);
    }
    auto panel = h.panel();
    auto list = h.list(panel, false);
    auto previous = findAction(list, "pagePrevious");
    auto next = findAction(list, "pageNext");
    expect_true(previous && next, "overflowing rows must expose separate previous and next paging controls");
    auto firstPage = visibleRowLabels(h, list);
    expect_true(firstPage.size() == static_cast<std::size_t>(list->getSizeY(h.gui)),
                "row paging must use the full visible height for item rows");
    if (!previous || !next)
        return;
    std::set<std::string> seen = firstPage;
    for (int page = 0; page < 4; ++page) {
        clickWidget(h.gui, next);
        auto labels = visibleRowLabels(h, list);
        seen.insert(labels.begin(), labels.end());
    }
    expect_true(seen == expected, "clicking Next must make every item reachable without keyboard or wheel input");
    for (int page = 0; page < 4; ++page)
        clickWidget(h.gui, previous);
    expect_true(visibleRowLabels(h, list) == firstPage, "clicking Previous must return to the original first page");
}

void testManualMovementAndWaitCancelOldDestinationPreview() {
    NavigationHarness h;
    auto world = std::make_shared<CMapGraphicsObject>();
    world->setGame(h.game);
    world->setLayout(fixedLayout(0, 0, 1200, 800));
    h.gui->pushChild(world);
    const auto initial = h.player->getCoords();
    world->previewDestination(h.gui, Coords(6, 0, 0));
    expect_true(h.player->getCoords() == initial, "previewing a destination must not move the player");
    keyEvent(h.gui, SDLK_RIGHT);
    const auto afterStep = h.player->getCoords();
    const auto turnAfterStep = h.map->getTurn();
    expect_true(afterStep != initial, "manual movement regression must drive a real player step");
    keyEvent(h.gui, SDLK_RETURN);
    expect_true(h.player->getCoords() == afterStep && h.map->getTurn() == turnAfterStep,
                "Enter after a manual step must not commit an obsolete route preview");
    world->previewDestination(h.gui, Coords(7, 0, 0));
    keyEvent(h.gui, SDLK_SPACE);
    const auto afterWait = h.player->getCoords();
    const auto turnAfterWait = h.map->getTurn();
    keyEvent(h.gui, SDLK_RETURN);
    expect_true(h.player->getCoords() == afterWait && h.map->getTurn() == turnAfterWait,
                "Wait must cancel a pending preview instead of leaving a hidden travel command");
}

void testResponsivePageNavigationRequiresAMatchingHeaderClick() {
    NavigationHarness h;
    auto panel = h.panel();
    panel->setLayout(fixedLayout(150, 80, 800, 700));
    auto first = std::make_shared<CWidget>();
    auto second = std::make_shared<CWidget>();
    first->setStringProperty("uiGroup", "1:Bag");
    second->setStringProperty("uiGroup", "2:Details");
    first->setLayout(fixedLayout(0, 120, 300, 400));
    second->setLayout(fixedLayout(320, 120, 300, 400));
    panel->addChild(first);
    panel->addChild(second);
    auto renderShell = [&]() { panel->renderShell(h.gui, panel->getLayout()->getRect(panel)); };
    renderShell();
    expect_true(first->isVisible() && !second->isVisible(), "a narrow panel must start on its first group");
    mouseEvent(h.gui, SDL_MOUSEBUTTONUP, 850, 160);
    renderShell();
    expect_true(first->isVisible(), "an unmatched release over the page header must not change the active group");
    mouseEvent(h.gui, SDL_MOUSEBUTTONDOWN, 1150, 160);
    mouseEvent(h.gui, SDL_MOUSEBUTTONUP, 1150, 160);
    renderShell();
    expect_true(first->isVisible(), "a click outside the panel's horizontal bounds must not change its group");
    mouseEvent(h.gui, SDL_MOUSEBUTTONDOWN, 850, 160);
    mouseEvent(h.gui, SDL_MOUSEBUTTONUP, 850, 160);
    renderShell();
    expect_true(!first->isVisible() && second->isVisible(), "a matched next-header click must reveal the next group");
}

void testMapAndPlayerReplacementInvalidatePendingTravel() {
    NavigationHarness h;
    auto world = std::make_shared<CMapGraphicsObject>();
    world->setGame(h.game);
    world->setLayout(fixedLayout(0, 0, 1200, 800));
    h.gui->pushChild(world);
    world->previewDestination(h.gui, Coords(6, 0, 0));
    auto replacementMap = std::make_shared<CMap>();
    replacementMap->setGame(h.game);
    h.map->detachPlayer();
    h.game->setMap(replacementMap);
    replacementMap->setPlayer(h.player);
    expect_true(!keyEvent(h.gui, SDLK_RETURN), "a map transition must remove the obsolete Enter travel action");

    world->previewDestination(h.gui, Coords(4, 0, 0));
    auto replacementPlayer = std::make_shared<CPlayer>();
    replacementPlayer->setGame(h.game);
    auto stats = std::make_shared<CStats>();
    stats->setMainStat("stamina");
    stats->setStamina(10);
    replacementPlayer->setBaseStats(stats);
    replacementMap->setPlayer(replacementPlayer);
    expect_true(!keyEvent(h.gui, SDLK_RETURN),
                "replacing the active player must remove a route selected by the previous player");
}

void testQuestRowsUseTheAuthoredQuestDescription() {
    NavigationHarness h;
    auto quest = std::make_shared<CQuest>();
    quest->setGame(h.game);
    quest->setName("uiNamedQuest");
    quest->setDescription("Return the lost amulet");
    quest->setObjective("Speak with the owner in town.");
    h.player->setQuests({quest});
    auto panel = std::make_shared<CGameQuestPanel>();
    panel->setGame(h.game);
    panel->setLayout(fixedLayout(100, 80, 900, 720));
    h.gui->pushChild(panel);
    auto list = std::make_shared<CListView>();
    list->setGame(h.game);
    list->setRows(true);
    list->setSearchable(true);
    list->setShowEmpty(false);
    list->setCollection("questCollection");
    list->setCallback("questCallback");
    list->setSelect("questSelect");
    list->setLayout(fixedLayout(40, 120, 500, 256));
    panel->addChild(list);
    list->initialize();
    vstd::event_loop<>::instance()->run();
    list->refresh();
    expect_true(visibleRowLabels(h, list) == std::set<std::string>{"Return the lost amulet"},
                "quest rows must render CQuest's authored description instead of its empty base description");
    h.gui->focusWidget(list);
    keyEvent(h.gui, SDLK_SLASH);
    list->textInput(h.gui, "amulet");
    expect_true(visibleRowLabels(h, list) == std::set<std::string>{"Return the lost amulet"},
                "quest search must match the same authored description displayed in its row");
}

void testRowPagerFitsEnlargedTextIndependentlyOfUiScale() {
    NavigationHarness h;
    const auto originalPreferences = h.gui->getUiPreferences();
    expect_true(h.gui->applyUiPreferences(R"({"uiScale":100,"textScale":200})"),
                "pager fixture must enlarge text independently of controls");
    for (int index = 0; index < 8; ++index)
        h.item("Pager relic " + std::to_string(index));
    auto panel = h.panel();
    auto list = h.list(panel, false);
    auto previous = findAction(list, "pagePrevious");
    expect_true(previous != nullptr, "overflowing text-scaled lists must keep a Previous control");
    if (previous) {
        const auto rect = previous->getLayout()->getRect(previous);
        const int textHeight = h.gui->getTextManager()->measureText("Previous", 0, "body").second;
        expect_true(rect->h >= textHeight + 16,
                    "pager controls must fit actual enlarged text plus padding when UI scale stays at 100 percent");
    }
    expect_true(h.gui->applyUiPreferences(originalPreferences), "pager fixture must restore preferences");
}
} // namespace

int main() {
    SDL_setenv("SDL_VIDEODRIVER", "dummy", 1);
    SDL_setenv("SDL_AUDIODRIVER", "dummy", 1);
    SDL_setenv("SDL_RENDER_DRIVER", "software", 1);
    const char *preferencesPath = "ui-navigation-test-preferences.json";
    std::remove(preferencesPath);
    SDL_setenv("GAME_UI_PREFERENCES_PATH", preferencesPath, 1);
    pybind11::scoped_interpreter guard{};
    type_registration::registerCoreTypes();
    type_registration::registerObjectTypes();
    type_registration::registerHandlerTypes();
    type_registration::registerGuiTypes();
    type_registration::registerGuiPanelTypes();
    type_registration::registerGuiWidgetTypes();
    type_registration::registerGuiAnimationTypes();
    testSearchTextDoesNotTriggerPanelHotkeys();
    testRowPagingHasWorkingPreviousAndNextControls();
    testManualMovementAndWaitCancelOldDestinationPreview();
    testResponsivePageNavigationRequiresAMatchingHeaderClick();
    testMapAndPlayerReplacementInvalidatePendingTravel();
    testQuestRowsUseTheAuthoredQuestDescription();
    testRowPagerFitsEnlargedTextIndependentlyOfUiScale();
    std::remove(preferencesPath);
    return finish_tests();
}
