/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026 Andrzej Lis
SPDX-License-Identifier: GPL-3.0-or-later
*/
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CJsonUtil.h"
#include "core/CMap.h"
#include "core/CStats.h"
#include "core/CTypeRegistration.h"
#include "core/CTypes.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/CTextManager.h"
#include "gui/CDetailViewport.h"
#include "gui/object/CWidget.h"
#include "gui/object/CStatsGraphicsObject.h"
#include "gui/panel/CGameCharacterPanel.h"
#include "gui/panel/CGameFightPanel.h"
#include "gui/panel/CGameInventoryPanel.h"
#include "gui/panel/CGameLootPanel.h"
#include "gui/panel/CGameQuestPanel.h"
#include "gui/panel/CGameTradePanel.h"
#include "gui/panel/CGameTextPanel.h"
#include "gui/panel/CCreatureView.h"
#include "handler/CFightHandler.h"
#include "handler/CTooltipHandler.h"
#include "handler/CObjectHandler.h"
#include "object/CInteraction.h"
#include "object/CItem.h"
#include "object/CMarket.h"
#include "object/CPlayer.h"
#include "object/CQuest.h"
#include "object/CEffect.h"
#include "object/CCreatureClass.h"
#include "object/CCreatureClassTrack.h"
#include "object/CCreatureRace.h"
#include "object/CCreatureTemplate.h"
#include "test_harness.h"

#include <algorithm>
#include <cstdio>
#include <pybind11/embed.h>

namespace {
struct ManagementHarness {
    std::shared_ptr<CGame> game = std::make_shared<CGame>();
    std::shared_ptr<CMap> map = std::make_shared<CMap>();
    std::shared_ptr<CGui> gui = std::make_shared<CGui>();
    std::shared_ptr<CPlayer> player = std::make_shared<CPlayer>();

    ManagementHarness() {
        for (const auto &[name, builder] : *CTypes::builders()) {
            game->getObjectHandler()->registerType(name, builder);
        }
        game->getObjectHandler()->registerConfig("slotConfiguration", CJsonUtil::from_string(R"({
            "class": "CSlotConfig", "properties": {"configuration": {
                "0": {"class": "CSlot", "properties": {"slotName": "RightHand", "types": ["CWeapon"]}},
                "1": {"class": "CSlot", "properties": {"slotName": "Head", "types": ["CHelmet"]}}
            }}})",
                                                                                             "slotConfiguration"));
        game->getObjectHandler()->registerConfig(
            "mapObjectPriorities", CJsonUtil::from_string(R"({"class":"CMapStringInt","properties":{"values":{}}})"));
        game->setMap(map);
        game->setGui(gui);
        map->setGame(game);
        gui->setGame(game);
        player->setGame(game);
        auto stats = std::make_shared<CStats>();
        stats->setMainStat("stamina");
        stats->setStamina(10);
        player->setBaseStats(stats);
        map->setPlayer(player);
        player->setHp(player->getHpMax() - 1);
        player->setMana(player->getManaMax());
    }

    ~ManagementHarness() { game->getContext()->shutdown(); }

    std::shared_ptr<CPotion> potion(const std::string &name) {
        auto item = std::make_shared<CPotion>();
        item->setGame(game);
        item->setName(name);
        item->setTypeId("uiHealingPotion");
        item->setLabel("Healing potion");
        item->addTag(CTag::Heal);
        player->addItem(item);
        return item;
    }
};

void testInventoryInspectionNeverConsumesAnItem() {
    ManagementHarness h;
    auto panel = std::make_shared<CGameInventoryPanel>();
    auto potion = h.potion("inspectPotion");
    panel->inventoryCallback(h.gui, 0, potion);
    panel->inventoryCallback(h.gui, 0, potion);
    expect_true(h.player->hasInInventory(potion), "repeated item inspection must not use a potion");
    expect_true(!panel->inventoryRightClickCallback(h.gui, 0, potion), "right click must allow tooltip inspection");
    expect_true(h.player->hasInInventory(potion), "right click inspection must not consume a potion");
    expect_true(panel->getSelectionDetails(h.gui).find("Healing potion") != std::string::npos,
                "selection must expose a persistent item name");
    panel->useSelected(h.gui);
    expect_true(!h.player->hasInInventory(potion), "the explicit Use action must use the selected potion");
    const auto count = h.player->getItems().size();
    panel->useSelected(h.gui);
    expect_true(h.player->getItems().size() == count, "repeating Use after consumption must not consume another item");

    auto fullPotion = h.potion("fullPotion");
    h.player->setHp(h.player->getHpMax());
    panel->inventoryCallback(h.gui, 0, fullPotion);
    panel->useSelected(h.gui);
    expect_true(h.player->hasInInventory(fullPotion), "explicit use must retain the full-health potion guard");
    expect_true(panel->getSelectionDetails(h.gui).find("Health is full") != std::string::npos,
                "full-resource restrictions must be visible");
    fullPotion->addTag(CTag::Quest);
    h.player->setHp(h.player->getHpMax() - 1);
    panel->useSelected(h.gui);
    expect_true(h.player->hasInInventory(fullPotion), "quest items must remain inspectable without being usable");
}

void testEquipmentRequiresAnExplicitActionAndKeepsCurses() {
    ManagementHarness h;
    auto panel = std::make_shared<CGameInventoryPanel>();
    auto weapon = std::make_shared<CWeapon>();
    weapon->setGame(h.game);
    weapon->setName("uiWeapon");
    weapon->setLabel("Cursed blade");
    weapon->getBonus()->setStrength(5);
    h.player->addItem(weapon);
    panel->inventoryCallback(h.gui, 0, weapon);
    panel->equippedCallback(h.gui, 0, nullptr);
    expect_true(!h.player->getItemAtSlot("0"), "selecting an equipment slot must not equip an item");
    panel->equipSelected(h.gui);
    expect_true(h.player->getItemAtSlot("0") == weapon, "Equip must move the selected weapon into its fitting slot");
    weapon->addTag(CTag::Cursed);
    panel->equippedCallback(h.gui, 0, weapon);
    panel->unequipSelected(h.gui);
    expect_true(h.player->getItemAtSlot("0") == weapon, "cursed equipment must stay locked");
    expect_true(panel->getSelectionDetails(h.gui).find("Cursed") != std::string::npos,
                "the equipment inspector must explain its curse");
    auto alternative = std::make_shared<CWeapon>();
    alternative->setGame(h.game);
    alternative->setName("uiAlternativeWeapon");
    alternative->getBonus()->setStrength(2);
    h.player->addItem(alternative);
    panel->inventoryCallback(h.gui, 0, alternative);
    expect_true(panel->getSelectionDetails(h.gui).find("Strength: -3") != std::string::npos,
                "equipment comparison must show the signed difference against the actual equipped bonus");
    weapon->removeTag(CTag::Cursed);
    panel->equippedCallback(h.gui, 0, weapon);
    panel->unequipSelected(h.gui);
    expect_true(h.player->hasInInventory(weapon), "Unequip must work after the curse is lifted");
    weapon->setCoveredSlots({"1"});
    panel->inventoryCallback(h.gui, 0, weapon);
    panel->equipSelected(h.gui);
    panel->equippedCallback(h.gui, 1, nullptr);
    expect_true(panel->getSelectionDetails(h.gui).find("Occupied by Cursed blade") != std::string::npos,
                "an empty-looking slot covered by a compound artifact must explain its actual occupant");
    panel->setGame(h.game);
    auto panelLayout = std::make_shared<CLayout>();
    panelLayout->setRect(0, 0, 900, 700);
    panel->setLayout(panelLayout);
    h.gui->pushChild(panel);
    auto slots = std::make_shared<CListView>();
    slots->setGame(h.game);
    slots->setRows(true);
    slots->setShowEmpty(true);
    slots->setCollection("equippedCollection");
    auto slotLayout = std::make_shared<CLayout>();
    slotLayout->setRect(0, 0, 400, 350);
    slots->setLayout(slotLayout);
    panel->addChild(slots);
    bool coveredLabel = false;
    for (const auto &graphic : slots->getProxiedObjects(h.gui, 0, 1)) {
        if (auto label = vstd::cast<CTextWidget>(graphic))
            coveredLabel = coveredLabel || label->getText().find("Covered by Cursed blade") != std::string::npos;
    }
    expect_true(coveredLabel, "compound-covered equipment rows must identify their occupying artifact");
}

void testCombatInspectionAndUnavailableActionFeedback() {
    ManagementHarness h;
    auto panel = std::make_shared<CGameFightPanel>();
    auto potion = h.potion("combatPotion");
    panel->itemsCallback(h.gui, 0, potion);
    panel->itemsCallback(h.gui, 0, potion);
    expect_true(!panel->itemsRightClickCallback(h.gui, 0, potion), "combat right click must inspect");
    expect_true(h.player->hasInInventory(potion), "combat inspection must not consume items");
    panel->useSelectedItem(h.gui);
    expect_true(!h.player->hasInInventory(potion), "combat explicit Use must preserve item behavior");

    auto action = std::make_shared<CInteraction>();
    action->setLabel("Frost bolt");
    action->setManaCost(h.player->getMana() + 4);
    panel->interactionsCallback(h.gui, 0, action);
    panel->interactionsCallback(h.gui, 0, action);
    expect_true(panel->interactionsSelect(h.gui, 0, action), "an unaffordable action must remain inspectable");
    expect_true(panel->getSelectionDetails(h.gui).find("Needs 4 more mana") != std::string::npos,
                "the action inspector must explain the exact mana shortage");
    const auto details = panel->getSelectionDetails(h.gui);
    const auto costPosition = details.find("Mana cost:");
    expect_true(costPosition != std::string::npos && details.find("Mana cost:", costPosition + 1) == std::string::npos,
                "the action inspector must show its authoritative mana cost exactly once");
    panel->cancel();
    panel->executeSelectedAction(h.gui);
    expect_true(panel->isCancelled(), "an explicit action must not revive a cancelled encounter");
}

void testCombatLogIsBoundedOrderedAndReadOnly() {
    ManagementHarness h;
    h.game->getObjectHandler()->registerConfig("infoPanel", CJsonUtil::from_string(R"({
        "class":"CGameTextPanel","properties":{"layout":{"class":"CLayout",
        "properties":{"x":"20","y":"20","w":"860","h":"620"}}}})"));
    for (int index = 0; index < 70; ++index)
        CFightHandler::recordCombatStatus(h.map, "Event " + std::to_string(index) + ": " + std::string(100, 'x'));
    const auto history = CFightHandler::getCombatHistory(h.map);
    expect_true(history.size() == CFightHandler::CombatHistoryLimit && history.front().starts_with("Event 6:") &&
                    history.back().starts_with("Event 69:"),
                "combat history must retain the newest 64 exact events in chronological order");
    h.map->setNumericProperty("combatRound", 21);
    auto panel = std::make_shared<CGameFightPanel>();
    panel->setGame(h.game);
    panel->setTypeId("fightPanel");
    panel->setCloseable(false);
    auto layout = std::make_shared<CLayout>();
    layout->setRect(0, 0, 900, 700);
    panel->setLayout(layout);
    auto button = std::make_shared<CButton>();
    button->setGame(h.game);
    button->setText("Combat log [L]");
    button->setClick("showCombatLog");
    auto buttonLayout = std::make_shared<CLayout>();
    buttonLayout->setRect(24, 600, 270, 60);
    button->setLayout(buttonLayout);
    panel->addChild(button);
    h.gui->pushChild(panel);
    auto item = h.potion("logInspectedItem");
    panel->itemsCallback(h.gui, 0, item);
    h.gui->focusWidget(button);
    const auto turn = h.map->getTurn();
    const auto mana = h.player->getMana();
    const auto hp = h.player->getHp();
    const auto status = panel->getCombatStatus(h.gui);
    expect_true(status.starts_with("Round 21\nEvent 69:"), "the current status must retain the authoritative round");
    for (int frame = 0; frame < 4; ++frame) {
        panel->renderCombatStatus(h.gui, CUtil::rect(0, 0, 700, 100), 0);
        panel->getCombatLog(h.gui);
    }
    expect_true(CFightHandler::getCombatHistory(h.map) == history,
                "redrawing and reading combat history must never append duplicate events");

    auto key = [&](SDL_Keycode code, bool repeat = false) {
        SDL_Event event{};
        event.type = SDL_KEYDOWN;
        event.key.keysym.sym = code;
        event.key.repeat = repeat;
        h.gui->event(&event);
        if (!repeat) {
            event.type = SDL_KEYUP;
            h.gui->event(&event);
        }
    };
    SDL_Event enter{};
    enter.type = SDL_KEYDOWN;
    enter.key.keysym.sym = SDLK_RETURN;
    h.gui->event(&enter);
    auto reader = vstd::cast<CGameTextPanel>(h.gui->findChild("CGameTextPanel"));
    expect_true(reader && reader->getTitle() == "Combat log", "keyboard activation must open the shared log reader");
    if (!reader)
        return;
    expect_true(reader->getText().size() > 4096 && reader->getText().find("Event 69:") != std::string::npos,
                "the scrollable combat reader must receive complete history beyond 4096 bytes");
    enter.key.repeat = 1;
    h.gui->event(&enter);
    expect_true(reader->isAttachedToGui(h.gui), "the opening activation cannot also dismiss the combat reader");
    enter.type = SDL_KEYUP;
    h.gui->event(&enter);
    panel->showCombatLog(h.gui);
    expect_true(h.gui->getChildren().size() == 2, "repeated log opening must not stack duplicate readers");
    std::static_pointer_cast<CGamePanel>(reader)->renderObject(h.gui, reader->getLayout()->getRect(reader), 0);
    key(SDLK_PAGEDOWN);
    key(SDLK_ESCAPE);
    expect_true(!reader->isAttachedToGui(h.gui) && h.gui->isFocused(button.get()) && !panel->isCancelled(),
                "closing the log must restore combat focus without cancelling the encounter");
    expect_true(h.map->getTurn() == turn && h.player->getMana() == mana && h.player->getHp() == hp &&
                    h.player->hasInInventory(item) && panel->itemsSelect(h.gui, 0, item) &&
                    CFightHandler::getCombatHistory(h.map) == history && panel->getCombatStatus(h.gui) == status,
                "reading and cancelling combat history must preserve turns, resources, selection and status");

    SDL_Event click{};
    click.type = SDL_MOUSEBUTTONDOWN;
    click.button.button = SDL_BUTTON_LEFT;
    click.button.x = 60;
    click.button.y = 620;
    h.gui->event(&click);
    click.type = SDL_MOUSEBUTTONUP;
    h.gui->event(&click);
    reader = vstd::cast<CGameTextPanel>(h.gui->findChild("CGameTextPanel"));
    expect_true(reader != nullptr, "the visible Combat log control must also work with the mouse");
    key(SDLK_ESCAPE);
    auto search = std::make_shared<CListView>();
    search->setGame(h.game);
    search->setRows(true);
    search->setSearchable(true);
    search->setCollection("itemsCollection");
    auto searchLayout = std::make_shared<CLayout>();
    searchLayout->setRect(24, 180, 400, 250);
    search->setLayout(searchLayout);
    panel->addChild(search);
    h.gui->focusWidget(search);
    key(SDLK_SLASH);
    key(SDLK_l);
    SDL_Event textInput{};
    textInput.type = SDL_TEXTINPUT;
    textInput.text.text[0] = 'l';
    h.gui->event(&textInput);
    expect_true(search->isSearching() && search->getViewState().query == "l" && !h.gui->findChild("CGameTextPanel"),
                "typing l into combat search must not trigger the log shortcut");
    key(SDLK_ESCAPE);
    h.gui->focusWidget(button);
    key(SDLK_l);
    reader = vstd::cast<CGameTextPanel>(h.gui->findChild("CGameTextPanel"));
    expect_true(reader != nullptr, "the L shortcut must open the combat log");
    auto nextMap = std::make_shared<CMap>();
    nextMap->setGame(h.game);
    h.game->setMap(nextMap);
    expect_true(!panel->isAttachedToGui(h.gui) && (!reader || !reader->isAttachedToGui(h.gui)) &&
                    CFightHandler::getCombatHistory(nextMap).empty(),
                "scene transitions must dismiss the old combat reader and show no previous-map history");
    expect_true(CFightHandler::getCombatHistory(h.map) == history && h.map->getNumericProperty("combatRound") == 21,
                "panel teardown must not erase encounter history or its authoritative round");
    CFightHandler::resetCombatHistory(h.map);
    expect_true(CFightHandler::getCombatHistory(h.map).empty() && h.map->getNumericProperty("combatRound") == 0,
                "starting another encounter must reset the retained history and round");
}

void testTradeInspectionAndExactQuantities() {
    ManagementHarness h;
    auto panel = std::make_shared<CGameTradePanel>();
    auto market = std::make_shared<CMarket>();
    market->setBuy(50);
    market->setSell(100);
    panel->setMarket(market);
    expect_true(!panel->inventorySelect(h.gui, 0, nullptr) && !panel->marketSelect(h.gui, 0, nullptr),
                "empty trade rows must never be highlighted as inspected items");
    auto first = h.potion("tradePotionOne");
    auto second = h.potion("tradePotionTwo");
    panel->inventoryCallback(h.gui, 0, first);
    panel->inventoryCallback(h.gui, 0, first);
    expect_true(panel->getTotalSellCost() == 0, "trade inspection must not add a whole stack to sale");
    panel->addSelectedForSale(h.gui);
    expect_true(panel->getTotalSellCost() == market->getBuyCost(first), "Add to sale must add exactly one copy");
    expect_true(panel->getTradeSummary(h.gui).find("(1 item)") != std::string::npos,
                "a single-item transaction must use singular item wording");
    panel->addSelectedForSale(h.gui);
    expect_true(panel->getTotalSellCost() == market->getBuyCost(first) + market->getBuyCost(second),
                "a second Add action must add the second exact copy");
    expect_true(panel->getTradeSummary(h.gui).find("(2 items)") != std::string::npos,
                "multiple-item transactions must retain plural wording");
    expect_true(panel->getTradeSummary(h.gui).find("Sale total: " + std::to_string(panel->getTotalSellCost())) !=
                        std::string::npos &&
                    panel->getTradeSummary(h.gui).find(
                        "Gold after sale: " + std::to_string(h.player->getGold() + panel->getTotalSellCost())) !=
                        std::string::npos,
                "the pending sale must show the exact total and resulting balance before confirmation");
    panel->addSelectedForSale(h.gui);
    expect_true(panel->getTradeSummary(h.gui).find("No more sellable copies") != std::string::npos,
                "exhausted stacks must explain why another copy cannot be added");
    panel->clearSelection(h.gui);
    expect_true(panel->getTotalSellCost() == 0, "Clear must reset the pending transaction without selling");
    expect_true(h.player->hasInInventory(first) && h.player->hasInInventory(second),
                "selection changes must preserve ownership");
    auto stock = std::make_shared<CWeapon>();
    stock->setName("merchantWeapon");
    stock->setTypeId("merchantWeapon");
    stock->setLabel("Iron blade");
    stock->setDescription(std::string(800, 'x'));
    market->add(stock);
    panel->marketCallback(h.gui, 0, stock);
    expect_true(panel->getTotalBuyCost() == 0, "merchant inspection must not add a purchase");
    panel->addSelectedForPurchase(h.gui);
    expect_true(panel->getTotalBuyCost() == market->getSellCost(stock),
                "Add to purchase must show the authoritative price");
    expect_true(panel->getTradeSummary(h.gui).find("more gold") != std::string::npos,
                "an unaffordable basket must expose its shortage before purchase");
    const auto summary = panel->getTradeSummary(h.gui);
    expect_true(summary.find("Buy price:") < summary.find(stock->getDescription()) &&
                    summary.find("Purchase total:") < summary.find(stock->getDescription()) &&
                    summary.find("more gold") < summary.find(stock->getDescription()),
                "prices, totals and requirements must appear before long item prose");
    market->remove(stock);
    panel->finalizeBuy(h.gui);
    expect_true(panel->getTradeSummary(h.gui).find("selected items changed") != std::string::npos,
                "removed merchant stock must reject a stale basket before opening confirmation");
    panel->clearSelection(h.gui);
    panel->inventoryCallback(h.gui, 0, first);
    panel->addSelectedForSale(h.gui);
    first->addTag(CTag::Quest);
    second->addTag(CTag::Quest);
    panel->finalizeSell(h.gui);
    expect_true(panel->getTradeSummary(h.gui).find("selected items changed") != std::string::npos,
                "items that become protected must reject stale sale selections");
    expect_true(h.player->hasInInventory(first) && !market->getItems().count(first),
                "a rejected sale must preserve item ownership");
}

void testCharacterIdentityAndSignedItemDetails() {
    ManagementHarness h;
    auto panel = std::make_shared<CGameCharacterPanel>();
    auto sheet = std::make_shared<CMapStringString>();
    sheet->setValues({{"Race", "getRaceId"}, {"Class", "getPlayerClassId"}});
    panel->setCharSheet(sheet);
    h.player->setTypeId("Warrior");
    h.player->setLabel("Warrior");
    auto lines = panel->buildCharacterSheetLines(h.player);
    expect_true(std::count_if(lines.begin(), lines.end(), [](const auto &row) { return row.first == "Race"; }) == 1,
                "character identity must contain exactly one race row");
    expect_true(std::count_if(lines.begin(), lines.end(), [](const auto &row) { return row.first == "Class"; }) == 1,
                "character identity must contain exactly one class row");
    auto item = std::make_shared<CItem>();
    item->setLabel("Burdened relic");
    item->getBonus()->setStrength(-3);
    item->getBonus()->setArmor(2);
    item->setCoveredSlots({"1", "2"});
    auto tooltip = CTooltipHandler::buildTooltip(item);
    expect_true(tooltip.find("-3") != std::string::npos && tooltip.find("+2") != std::string::npos,
                "item inspection must show penalties and bonuses with their signs");
    expect_true(tooltip.find("3 equipment slots") != std::string::npos,
                "combined artifact occupancy must be explained");
    expect_true(CTooltipHandler::buildTooltip(nullptr).empty(), "an expired inspector target must fail closed");
}

void testJournalTabsTrackingAndRewardAcknowledgement() {
    ManagementHarness h;
    auto active = std::make_shared<CQuest>();
    active->setName("uiActiveQuest");
    active->setDescription("Find the sealed gate.");
    auto completed = std::make_shared<CQuest>();
    completed->setName("uiCompletedQuest");
    completed->setDescription("Reach the village.");
    h.player->setQuests({active});
    h.player->setCompletedQuests({completed});
    auto journal = std::make_shared<CGameQuestPanel>();
    expect_true(journal->getText(h.gui).find("Find the sealed gate") != std::string::npos,
                "the journal must open on active quests");
    expect_true(journal->getText(h.gui).find("Reach the village") == std::string::npos,
                "completed quests must not crowd the active tab");
    expect_true(journal->questCollection(h.gui)->size() == 1,
                "the journal's left list must contain only the selected tab's quests");
    journal->questCallback(h.gui, 0, active);
    expect_true(journal->getSelectedQuestText(h.gui).find("Find the sealed gate") != std::string::npos,
                "the journal's right detail must inspect the selected quest");
    journal->trackSelectedQuest(h.gui);
    expect_true(h.player->getStringProperty("uiTrackedQuestId") == "uiActiveQuest",
                "the Track action must operate on the selected active quest");
    expect_true(journal->setTrackedQuest(h.gui, "uiActiveQuest"), "an active quest can be tracked");
    expect_true(!journal->setTrackedQuest(h.gui, "uiCompletedQuest"),
                "a completed quest cannot become the tracked objective");
    expect_true(h.player->getStringProperty("uiTrackedQuestId") == "uiActiveQuest",
                "tracking must persist through a save-compatible player property");
    journal->showCompleted(h.gui);
    expect_true(journal->getText(h.gui).find("Reach the village") != std::string::npos,
                "the completed tab must expose completed objectives");
    h.player->setStringProperty("uiDialogueHistory", R"([{"speaker":"Warden","text":"The gate is sealed."}])");
    journal->showHistory(h.gui);
    expect_true(journal->getText(h.gui).find("The gate is sealed") != std::string::npos,
                "history must display recorded dialogue without replaying actions");
    auto rewards = std::make_shared<CGameLootPanel>();
    expect_true(rewards->getRewardsText().find("No items") != std::string::npos, "empty loot must be explicit");
    auto reward = std::make_shared<CItem>();
    reward->setLabel("Ancient seal");
    rewards->setItems({reward});
    expect_true(rewards->getRewardsText().find("Ancient seal") != std::string::npos,
                "rewards must have readable names");
    std::set<std::shared_ptr<CItem>> groupedRewards{reward};
    for (int i = 0; i < 3; ++i) {
        auto scroll = std::make_shared<CItem>();
        scroll->setLabel("Scroll");
        groupedRewards.insert(scroll);
    }
    rewards->setItems(groupedRewards);
    expect_true(rewards->getRewardsText() ==
                    "These rewards will be added to your inventory.\n\n1 x Ancient seal\n3 x Scroll\n",
                "reward receipts must render each distinct label once with its actual quantity");
    rewards->collectRewards(h.gui);
    expect_true(!h.player->hasInInventory(reward),
                "the reward panel must leave granting to the original caller after dismissal");
}

void testDefeatReceiptRecordsActualLossesAfterRecovery() {
    ManagementHarness h;
    auto lost = h.potion("lostPotion");
    auto questItem = h.potion("retainedQuestPotion");
    questItem->addTag(CTag::Quest);
    auto winner = std::make_shared<CCreature>();
    winner->setGame(h.game);
    winner->setName("uiEncounterWinner");
    auto stats = std::make_shared<CStats>();
    stats->setMainStat("stamina");
    stats->setStamina(10);
    winner->setBaseStats(stats);
    winner->setHp(winner->getHpMax());
    h.map->addObject(winner);
    h.player->setHp(0);
    CFightHandler::defeatedCreature(winner, h.player);
    expect_true(h.player->getHp() == 1 && h.player->getCoords() == h.map->getEntry(),
                "defeat receipt must preserve original one-HP entrance recovery");
    expect_true(winner->hasInInventory(lost) && h.player->hasInInventory(questItem),
                "defeat receipt must preserve winner loot and quest-item retention");
    const auto receipt = json::parse(h.player->getStringProperty("uiDefeatReceipt"));
    expect_true(receipt["lostItemCount"].get<int>() == 1 && receipt["hp"].get<int>() == 1,
                "the receipt must record exact losses and the resolved recovery HP");
    expect_true(receipt["lostItems"].size() == 1 &&
                    receipt["lostItems"][0]["label"].get<std::string>() == lost->getLabel(),
                "the receipt must not invent losses from generated winner loot or retained quest items");
}

void testLongRewardReceiptRendersItsFinalItemWithoutGrantingIt() {
    ManagementHarness h;
    auto rewards = std::make_shared<CGameLootPanel>();
    std::set<std::shared_ptr<CItem>> items;
    for (int i = 0; i < 240; ++i) {
        auto item = std::make_shared<CItem>();
        item->setLabel("Recovered relic " + std::to_string(1000 + i) + " from the forgotten archive");
        items.insert(item);
    }
    auto finalItem = std::make_shared<CItem>();
    finalItem->setLabel("ZZZ Final receipt reward A");
    items.insert(finalItem);
    rewards->setItems(items);
    const auto text = rewards->getRewardsText();
    expect_true(text.size() > 4096 && text.ends_with("1 x ZZZ Final receipt reward A\n"),
                "the long receipt fixture must put its final item beyond the text texture byte limit");
    const auto bounds = CUtil::rect(20, 20, 600, 180);
    rewards->renderRewards(h.gui, bounds, 0);
    const auto turn = h.map->getTurn();
    const auto inventory = h.player->getItems();
    rewards->mouseWheelEvent(h.gui, SDL_MOUSEWHEEL, bounds->x + 1, bounds->y + 1, 0, -1000000);
    auto captureEnding = [&] {
        SDL_SetRenderDrawColor(h.gui->getRenderer(), 0, 0, 0, 255);
        SDL_RenderClear(h.gui->getRenderer());
        rewards->renderRewards(h.gui, bounds, 0);
        std::vector<Uint32> pixels(bounds->w * bounds->h);
        expect_true(SDL_RenderReadPixels(h.gui->getRenderer(), bounds.get(), SDL_PIXELFORMAT_RGBA32, pixels.data(),
                                         bounds->w * sizeof(Uint32)) == 0,
                    "the offscreen receipt viewport must be readable for pixel comparison");
        return pixels;
    };
    const auto firstEnding = captureEnding();
    finalItem->setLabel("ZZZ Final receipt reward B");
    const auto changedEnding = captureEnding();
    expect_true(firstEnding != changedEnding,
                "scrolling to the receipt ending must render the actual final item beyond 4096 bytes");
    expect_true(h.map->getTurn() == turn && h.player->getItems() == inventory && rewards->getItems() == items,
                "reading and scrolling a long receipt must neither spend turns nor grant or discard items");
    rewards->collectRewards(h.gui);
    rewards->collectRewards(h.gui);
    expect_true(h.player->getItems() == inventory,
                "repeated receipt acknowledgements must leave the existing caller in charge of granting rewards");
}

void testRewardReceiptKeepsMeasuredHeaderAndContinueVisible() {
    ManagementHarness h;
    const auto originalPreferences = h.gui->getUiPreferences();
    h.gui->setWidth(1280);
    h.gui->setHeight(720);
    h.gui->applyUiPreferences(R"({"uiScale":200,"textScale":200})");
    auto rewards = std::make_shared<CGameLootPanel>();
    rewards->setGame(h.game);
    rewards->setTitle("Rewards");
    auto layout = std::make_shared<CLayout>();
    layout->setRect(180, 94, 920, 532);
    rewards->setLayout(layout);
    h.gui->pushChild(rewards);
    auto receipt = std::make_shared<CWidget>();
    receipt->setStringProperty("render", "renderRewards");
    auto receiptLayout = std::make_shared<CLayout>();
    receiptLayout->setRect(37, 90, 846, 351);
    receipt->setLayout(receiptLayout);
    rewards->addChild(receipt);
    auto proceed = std::make_shared<CButton>();
    proceed->setText("Continue");
    proceed->setStringProperty("click", "collectRewards");
    auto buttonLayout = std::make_shared<CLayout>();
    buttonLayout->setRect(589, 473, 294, 43);
    proceed->setLayout(buttonLayout);
    rewards->addChild(proceed);
    const auto bounds = layout->getRect(rewards);
    rewards->renderObject(h.gui, bounds, 0);
    const auto body = receiptLayout->getRect(receipt);
    const auto action = buttonLayout->getRect(proceed);
    const int labelHeight = h.gui->getTextManager()->measureText("Continue", action->w, "body").second;
    expect_true(body->y > bounds->y + rewards->getShellHeaderHeight(h.gui),
                "enlarged receipt text must start below the measured title and close control");
    expect_true(body->h >= labelHeight && body->y + body->h < action->y,
                "a compact receipt must preserve a scrollable body above its Continue action");
    expect_true(action->h >= labelHeight + UiTheme::scaled(h.gui, 16) && action->y + action->h <= bounds->y + bounds->h,
                "Continue must fit its enlarged label and remain inside the compact reward panel");
    h.gui->applyUiPreferences(originalPreferences);
}

void testCreatureStatusNamesAndDurationsAreInspectable() {
    auto creature = std::make_shared<CCreature>();
    expect_true(CCreatureView::getStatusText(creature) == "No active effects", "empty effects must be explicit");
    auto effect = std::make_shared<CEffect>();
    effect->setLabel("Poisoned");
    effect->setDuration(4);
    effect->setTimeLeft(2);
    creature->setEffects({effect});
    expect_true(CCreatureView::getStatusText(creature).find("Poisoned (2 turns)") != std::string::npos,
                "creature cards must show effect name and remaining duration");
    expect_true(CTooltipHandler::buildTooltip(effect).find("Remaining: 2 turns") != std::string::npos,
                "effect inspection must expose duration independently of the portrait layout");
    auto view = std::make_shared<CCreatureView>();
    expect_true(!view->getCreature(), "detached creature cards must safely handle missing scripts and GUI");
}

void testManagementButtonsExposeAuthoritativeAvailability() {
    ManagementHarness h;
    auto inventory = std::make_shared<CGameInventoryPanel>();
    auto button = [](const std::shared_ptr<CGamePanel> &panel, const std::string &action) {
        auto widget = std::make_shared<CButton>();
        widget->setClick(action);
        panel->addChild(widget);
        return widget;
    };
    auto use = button(inventory, "useSelected");
    auto equip = button(inventory, "equipSelected");
    auto unequip = button(inventory, "unequipSelected");
    const auto rect = CUtil::rect(0, 0, 1200, 900);
    inventory->renderObject(h.gui, rect, 0);
    expect_true(!use->getEnabled() && !equip->getEnabled() && !unequip->getEnabled(),
                "empty inventory selection must disable all three item actions");
    auto potion = h.potion("availabilityPotion");
    inventory->inventoryCallback(h.gui, 0, potion);
    expect_true(use->getEnabled(), "selection must update button availability before the next rendered frame");
    inventory->renderObject(h.gui, rect, 0);
    expect_true(use->getEnabled() && !equip->getEnabled(), "an injured player's potion must enable only Use");
    h.player->setHp(h.player->getHpMax());
    inventory->renderObject(h.gui, rect, 0);
    expect_true(!use->getEnabled() && inventory->getSelectionDetails(h.gui).find("Health is full") != std::string::npos,
                "full health must disable potion use and explain its restriction");
    h.player->setHp(h.player->getHpMax() - 1);
    potion->addTag(CTag::Quest);
    inventory->renderObject(h.gui, rect, 0);
    expect_true(!use->getEnabled(), "quest protection must disable use even when the resource is depleted");

    auto weapon = std::make_shared<CWeapon>();
    weapon->setGame(h.game);
    weapon->setName("availabilityBlade");
    h.player->addItem(weapon);
    inventory->inventoryCallback(h.gui, 0, weapon);
    inventory->renderObject(h.gui, rect, 0);
    expect_true(equip->getEnabled(), "compatible bag equipment must enable Equip");
    inventory->equipSelected(h.gui);
    weapon->addTag(CTag::Cursed);
    inventory->renderObject(h.gui, rect, 0);
    expect_true(!unequip->getEnabled(), "cursed equipment must visibly disable Unequip");

    auto fight = std::make_shared<CGameFightPanel>();
    auto execute = button(fight, "executeSelectedAction");
    auto useCombat = button(fight, "useSelectedItem");
    fight->renderObject(h.gui, rect, 0);
    expect_true(!execute->getEnabled() && !useCombat->getEnabled(), "unselected combat actions must be disabled");
    auto action = std::make_shared<CInteraction>();
    action->setManaCost(h.player->getMana() + 1);
    fight->interactionsCallback(h.gui, 0, action);
    fight->renderObject(h.gui, rect, 0);
    expect_true(!execute->getEnabled(), "unaffordable combat actions must remain disabled");

    auto trade = std::make_shared<CGameTradePanel>();
    auto addSale = button(trade, "addSelectedForSale");
    auto reviewSale = button(trade, "finalizeSell");
    auto reviewPurchase = button(trade, "finalizeBuy");
    trade->renderObject(h.gui, rect, 0);
    expect_true(!addSale->getEnabled() && !reviewSale->getEnabled() && !reviewPurchase->getEnabled(),
                "empty transaction selections must disable add and review controls");
    auto market = std::make_shared<CMarket>();
    market->setBuy(50);
    market->setSell(100);
    trade->setMarket(market);
    auto sale = h.potion("availabilitySale");
    trade->inventoryCallback(h.gui, 0, sale);
    expect_true(addSale->getEnabled(), "selecting stock must enable Add before another input event arrives");
    trade->renderObject(h.gui, rect, 0);
    expect_true(addSale->getEnabled() && !reviewSale->getEnabled(),
                "inspection must enable Add without enabling Review");
    trade->addSelectedForSale(h.gui);
    trade->renderObject(h.gui, rect, 0);
    expect_true(!addSale->getEnabled() && reviewSale->getEnabled(),
                "the final copy must disable Add and enable Review");

    expect_true(CTooltipHandler::getSlotLabel("RightHand") == "Right hand" &&
                    CTooltipHandler::getSlotLabel("LeftHand") == "Left hand",
                "equipment presentation must replace internal hand slot names with readable labels");
}

void testCompactCombatantCardsReserveReadableResourceBars() {
    ManagementHarness h;
    const auto originalPreferences = h.gui->getUiPreferences();
    expect_true(h.gui->applyUiPreferences(R"({"uiScale":200,"textScale":200})"),
                "compact combatant fixture must apply enlarged text");
    auto card = std::make_shared<CGameGraphicsObject>();
    auto layout = std::make_shared<CLayout>();
    layout->setRect(24, 208, 1152, 350);
    card->setLayout(layout);
    h.gui->addChild(card);
    auto portrait = std::make_shared<CCreatureView>();
    auto stats = std::make_shared<CStatsGraphicsObject>();
    portrait->setLayout(std::make_shared<CLayout>());
    stats->setLayout(std::make_shared<CLayout>());
    card->addChild(portrait);
    card->addChild(stats);
    CCreatureView::layoutCombatantCard(h.gui, card, h.player);
    const auto portraitRect = portrait->getLayout()->getRect(portrait);
    const auto statsRect = stats->getLayout()->getRect(stats);
    const auto cardRect = card->getLayout()->getRect(card);
    const int lineHeight = h.gui->getTextManager()->measureText("HP 999 / 999", 0, "small").second;
    expect_true(statsRect->h / 3 >= lineHeight && lineHeight > 0,
                "each HP, mana and XP bar must fit the current rendered text height at 200 percent");
    expect_true(portraitRect->x + portraitRect->w <= statsRect->x && portraitRect->h == cardRect->h,
                "a short wide card must place its portrait beside resource bars");
    expect_true(statsRect->y >= cardRect->y && statsRect->y + statsRect->h <= cardRect->y + cardRect->h,
                "compact resource bars must stay inside the available card height");
    expect_true(h.gui->applyUiPreferences(originalPreferences), "compact combatant test must restore preferences");
}

void testLegacyJournalReflowsWhenOnlyTextScaleChanges() {
    ManagementHarness h;
    const auto original = h.gui->getUiPreferences();
    h.gui->applyUiPreferences(R"({"uiScale":100,"textScale":100})");
    auto quest = std::make_shared<CQuest>();
    quest->setName("longJournalQuest");
    std::string description;
    for (int i = 0; i < 15; ++i) {
        description += "Read the discovered clues and recover the lost amulet.\n";
    }
    quest->setDescription(description + "Final discovered clue.");
    h.player->setQuests({quest});
    auto journal = std::make_shared<CGameQuestPanel>();
    auto layout = std::make_shared<CLayout>();
    layout->setRect(0, 0, 800, 600);
    journal->setLayout(layout);
    journal->getViewportText(h.gui);
    const auto originalMaximum = journal->getScrollMaximum();
    expect_true(originalMaximum > 0, "the journal regression fixture must overflow before scaling");
    h.gui->applyUiPreferences(R"({"uiScale":100,"textScale":200})");
    journal->getViewportText(h.gui);
    expect_true(journal->getScrollMaximum() > originalMaximum,
                "changing only text scale must invalidate journal paragraph heights");
    journal->keyboardEvent(h.gui, SDL_KEYDOWN, SDLK_END);
    expect_true(journal->getViewportText(h.gui).find("Final discovered clue") != std::string::npos,
                "the reflowed journal must allow reading its final paragraph");
    const int endOffset = journal->getScrollOffset();
    journal->showCompleted(h.gui);
    journal->getViewportText(h.gui);
    journal->showActive(h.gui);
    journal->getViewportText(h.gui);
    expect_true(journal->getScrollOffset() == endOffset,
                "the legacy journal must retain each tab's reading position when switching tabs");
    h.gui->applyUiPreferences(original);
}

void testJournalHistoryNavigationUsesTheVisibleDetailPane() {
    ManagementHarness h;
    auto journal = std::make_shared<CGameQuestPanel>();
    journal->setGame(h.game);
    auto layout = std::make_shared<CLayout>();
    layout->setRect(0, 0, 1000, 700);
    journal->setLayout(layout);
    for (int i = 0; i < 80; ++i) {
        h.gui->notify("History entry " + std::to_string(i) + ": " +
                      "A discovered road leads onward through the ruined valley. " +
                      "The next clue remains in the journal for later reading.");
    }
    journal->showHistory(h.gui);
    expect_true(journal->getSelectedQuestText(h.gui).size() > 4096,
                "the history fixture must exercise content beyond a single text texture");
    journal->renderSelectedQuest(h.gui, CUtil::rect(450, 100, 440, 180), 0);
    const auto turn = h.map->getTurn();
    journal->keyboardEvent(h.gui, SDL_KEYDOWN, SDLK_PAGEDOWN);
    const int pageOffset = journal->getDetailsScrollOffset();
    expect_true(pageOffset > 0, "Page Down must scroll the visible history pane");
    journal->keyboardEvent(h.gui, SDL_KEYDOWN, SDLK_END);
    const int endOffset = journal->getDetailsScrollOffset();
    expect_true(endOffset > pageOffset, "End must reach the end of the visible history pane");
    journal->keyboardEvent(h.gui, SDL_KEYDOWN, SDLK_DOWN);
    expect_true(journal->getDetailsScrollOffset() == endOffset, "Down must stop at the history's end");
    journal->keyboardEvent(h.gui, SDL_KEYDOWN, SDLK_UP);
    expect_true(journal->getDetailsScrollOffset() > 0 && journal->getDetailsScrollOffset() < endOffset,
                "Up must scroll the visible history pane toward earlier entries");
    journal->keyboardEvent(h.gui, SDL_KEYDOWN, SDLK_HOME);
    expect_true(journal->getDetailsScrollOffset() == 0, "Home must restore the first history viewport");
    journal->keyboardEvent(h.gui, SDL_KEYDOWN, SDLK_UP);
    expect_true(journal->getDetailsScrollOffset() == 0, "Up must stop at the history's beginning");
    journal->keyboardEvent(h.gui, SDL_KEYDOWN, SDLK_DOWN);
    const int lineOffset = journal->getDetailsScrollOffset();
    expect_true(lineOffset > 0 && lineOffset < pageOffset, "Down must move the visible history by a small step");
    journal->keyboardEvent(h.gui, SDL_KEYUP, SDLK_END);
    expect_true(journal->getDetailsScrollOffset() == lineOffset, "key releases must not scroll the history again");
    expect_true(journal->getScrollOffset() == 0 && h.map->getTurn() == turn,
                "detail navigation must leave the legacy viewport and game turn unchanged");
}

void testJournalTabsPreserveTheirOwnSelectionSearchAndScroll() {
    ManagementHarness h;
    auto journal = std::make_shared<CGameQuestPanel>();
    journal->setGame(h.game);
    auto layout = std::make_shared<CLayout>();
    layout->setRect(0, 0, 1000, 700);
    journal->setLayout(layout);
    h.gui->pushChild(journal);
    auto list = std::make_shared<CListView>();
    list->setGame(h.game);
    list->setCollection("questCollection");
    list->setCallback("questCallback");
    list->setRows(true);
    list->setSearchable(true);
    list->setShowEmpty(false);
    list->setAllowOversize(true);
    auto listLayout = std::make_shared<CLayout>();
    listLayout->setRect(0, 0, 440, 180);
    list->setLayout(listLayout);
    journal->addChild(list);
    std::set<std::shared_ptr<CQuest>> active;
    std::set<std::shared_ptr<CQuest>> completed;
    for (int i = 0; i < 12; ++i) {
        auto quest = std::make_shared<CQuest>();
        quest->setGame(h.game);
        quest->setName("retainedQuest" + std::to_string(i));
        quest->setDescription("Active quest " + std::to_string(i));
        quest->setObjective(std::string(500, 'x'));
        active.insert(quest);
        auto done = std::make_shared<CQuest>();
        done->setGame(h.game);
        done->setName("retainedDone" + std::to_string(i));
        done->setDescription("Completed quest " + std::to_string(i));
        done->setObjective(std::string(500, 'y'));
        completed.insert(done);
    }
    h.player->setQuests(active);
    h.player->setCompletedQuests(completed);
    list->refresh();
    h.gui->focusWidget(list);
    list->keyboardEvent(h.gui, SDL_KEYDOWN, SDLK_SLASH);
    list->textInput(h.gui, "Active");
    list->pageNext(h.gui);
    const auto activeList = list->getViewState();
    expect_true(activeList.offset > 0, "the active journal fixture must have a later list page");
    auto selectedActive = *active.rbegin();
    journal->questCallback(h.gui, 0, selectedActive);
    const auto detailsRect = CUtil::rect(450, 100, 440, 180);
    journal->renderSelectedQuest(h.gui, detailsRect, 0);
    journal->keyboardEvent(h.gui, SDL_KEYDOWN, SDLK_PAGEDOWN);
    const int activeDetails = journal->getDetailsScrollOffset();
    expect_true(activeDetails > 0, "the active quest fixture must scroll its detail text");
    journal->showCompleted(h.gui);
    expect_true(list->getViewState().query.empty(), "a newly opened completed tab must have its own empty query");
    h.gui->focusWidget(list);
    list->keyboardEvent(h.gui, SDL_KEYDOWN, SDLK_SLASH);
    list->textInput(h.gui, "Completed");
    list->pageNext(h.gui);
    list->pageNext(h.gui);
    const auto completedList = list->getViewState();
    auto selectedCompleted = *completed.rbegin();
    journal->questCallback(h.gui, 0, selectedCompleted);
    journal->renderSelectedQuest(h.gui, detailsRect, 0);
    journal->keyboardEvent(h.gui, SDL_KEYDOWN, SDLK_PAGEDOWN);
    const auto completedDetails = journal->getDetailsScrollOffset();
    journal->showHistory(h.gui);
    journal->showActive(h.gui);
    journal->renderSelectedQuest(h.gui, detailsRect, 0);
    expect_true(journal->questSelect(h.gui, 0, selectedActive) && journal->getDetailsScrollOffset() == activeDetails,
                "returning to Active must restore the selected quest and detail reading position");
    expect_true(list->getViewState().query == activeList.query && list->getViewState().offset == activeList.offset,
                "returning to Active must restore its search query and list page");
    journal->showCompleted(h.gui);
    journal->renderSelectedQuest(h.gui, detailsRect, 0);
    expect_true(journal->questSelect(h.gui, 0, selectedCompleted) &&
                    journal->getDetailsScrollOffset() == completedDetails,
                "Completed must retain its independent selected quest and reading position");
    expect_true(list->getViewState().query == completedList.query &&
                    list->getViewState().offset == completedList.offset,
                "Completed must retain its independent search query and list page");
}

void testCharacterModifierInspectionUsesTheActualCompositionSources() {
    ManagementHarness h;
    auto race = std::make_shared<CCreatureRace>();
    race->setLabel("Human");
    race->getBaseStats()->setStrength(2);
    race->getRacialLevelStats()->setStrength(1);
    h.player->setRace(race);
    h.player->setRacialLevel(2);
    auto creatureClass = std::make_shared<CCreatureClass>();
    creatureClass->setLabel("Warrior");
    creatureClass->getBaseStats()->setStrength(3);
    creatureClass->getLevelStats()->setStrength(2);
    h.player->setCreatureClass(creatureClass);
    h.player->setLevel(3);
    h.player->getBaseStats()->setStrength(4);
    h.player->getLevelStats()->setStrength(1);
    auto overlay = std::make_shared<CCreatureTemplate>();
    overlay->setLabel("Veteran");
    overlay->getStatAdjustments()->setStrength(5);
    h.player->setTemplates({overlay});
    auto weapon = std::make_shared<CWeapon>();
    weapon->setGame(h.game);
    weapon->setLabel("Old sword");
    weapon->getBonus()->setStrength(6);
    h.player->addItem(weapon);
    h.player->equipItem("0", weapon);
    auto effect = std::make_shared<CEffect>();
    effect->setLabel("Weakened");
    effect->setDuration(2);
    effect->setTimeLeft(2);
    effect->getBonus()->setStrength(-7);
    h.player->setEffects({effect});
    auto panel = std::make_shared<CGameCharacterPanel>();
    const auto text = panel->buildModifierSources(h.player);
    for (const auto &source : {"Race: Human", "Class: Warrior", "Hero base", "Race growth: Human (2 levels)",
                               "Class growth: Warrior (3 levels)", "Hero growth (3 levels)", "Trait: Veteran",
                               "Equipment: Old sword", "Effect: Weakened (2 turns remaining)"}) {
        expect_true(text.find(source) != std::string::npos,
                    (std::string("the inspector must name every actual stat source: ") + source).c_str());
    }
    expect_true(text.find("Strength: -7") != std::string::npos && h.player->getStats()->getStrength() == 24,
                "source inspection must preserve signed penalties and authoritative composition totals");
    expect_true(text.substr(text.find("Current totals")).find("Strength: +24") != std::string::npos,
                "the inspector total must come from the actual composed stats");
    auto trackClass = std::make_shared<CCreatureClass>();
    trackClass->setLabel("Ranger");
    trackClass->getBaseStats()->setStrength(10);
    trackClass->getLevelStats()->setStrength(4);
    auto track = std::make_shared<CCreatureClassTrack>();
    track->setCreatureClass(trackClass);
    track->setLevel(2);
    h.player->setClassTracks({track});
    const auto trackText = panel->buildModifierSources(h.player);
    expect_true(trackText.find("Warrior") == std::string::npos &&
                    trackText.find("Class growth: Ranger (2 levels)\nStrength: +8") != std::string::npos,
                "class tracks must replace the single class and use their own levels in inspection");
    expect_true(h.player->getStats()->getStrength() == 33,
                "read-only inspection must not mutate any source or compose class bonuses twice");
    h.game->getObjectHandler()->registerConfig("textPanel", CJsonUtil::from_string(R"({"class":"CGameTextPanel"})"));
    panel->inspectModifiers(h.gui);
    const auto children = h.gui->getChildren();
    auto reader = children.empty() ? nullptr : vstd::cast<CGameTextPanel>(*children.rbegin());
    expect_true(reader && reader->getTitle() == "Stat modifiers" && reader->getText() == trackText,
                "the inspection action must open a titled, read-only reader containing the actual sources");
}

void testWideInventoryPagingStaysAboveTheActionFooter() {
    for (const int scale : {1, 2}) {
        ManagementHarness h;
        h.gui->setWidth(1920 * scale);
        h.gui->setHeight(1080 * scale);
        h.gui->applyUiPreferences(R"({"uiScale":100,"textScale":100})");
        auto panel = std::make_shared<CGameInventoryPanel>();
        panel->setGame(h.game);
        auto shell = std::make_shared<CLayout>();
        shell->setRect(58 * scale, 33 * scale, 1804 * scale, 1015 * scale);
        panel->setLayout(shell);
        auto list = std::make_shared<CListView>();
        list->setGame(h.game);
        list->setCollection("inventoryCollection");
        list->setRows(true);
        list->setGrouping(false);
        list->setShowEmpty(false);
        list->setAllowOversize(true);
        list->setStringProperty("uiGroup", "1:Bag");
        auto listLayout = std::make_shared<CLayout>();
        listLayout->setRect(505 * scale, 223 * scale, 702 * scale, 660 * scale);
        list->setLayout(listLayout);
        panel->addChild(list);
        auto action = std::make_shared<CButton>();
        action->setText("Use");
        action->setBoolProperty("uiFooter", true);
        auto actionLayout = std::make_shared<CLayout>();
        actionLayout->setRect(883 * scale, 923 * scale, 270 * scale, 60 * scale);
        action->setLayout(actionLayout);
        panel->addChild(action);
        h.gui->pushChild(panel);
        for (int index = 0; index < 20; ++index)
            h.potion("pagedPotion" + std::to_string(index));
        panel->renderShell(h.gui, shell->getRect(panel));
        list->refresh();
        const auto footer = actionLayout->getRect(action);
        int pageControls = 0;
        for (const auto &child : list->getChildren()) {
            auto button = vstd::cast<CButton>(child);
            if (!button || !button->isVisible())
                continue;
            ++pageControls;
            const auto buttonRect = button->getLayout()->getRect(button);
            expect_true(buttonRect->y + buttonRect->h < footer->y,
                        "visible paging controls must remain fully above the action footer at 1080p and 4K");
        }
        expect_true(pageControls == 2, "the overflow fixture must render both actual paging controls");
        list->pageNext(h.gui);
        expect_true(list->getViewState().offset > 0, "the resized list must still reach its later items");
    }
}

void testDetailOverflowKeepsAVisibleCueAndFrontLoadsRestrictions() {
    ManagementHarness h;
    h.gui->applyUiPreferences(R"({"uiScale":200,"textScale":200})");
    auto rect = CUtil::rect(40, 200, 1100, 320);
    const auto shortContent = DetailViewport::contentRect(h.gui, rect, 100);
    expect_true(shortContent->h == rect->h, "short detail text must keep its full reading area");
    const auto longContent = DetailViewport::contentRect(h.gui, rect, 1600);
    const int hintHeight =
        h.gui->getTextManager()->measureText("Scroll: wheel / PgUp / PgDn - 100%", rect->w, "small").second;
    expect_true(longContent->h >= 200 && longContent->h + hintHeight < rect->h,
                "overflow details must reserve readable scroll guidance without covering body text");
    DetailViewport::drawScrollHint(h.gui, rect, longContent, 0, 1600 - longContent->h);
    DetailViewport::drawScrollHint(h.gui, rect, longContent, 1600 - longContent->h, 1600 - longContent->h);
    auto panel = std::make_shared<CGameInventoryPanel>();
    auto item = h.potion("longQuestItem");
    item->setDescription(std::string(800, 'x'));
    item->addTag(CTag::Quest);
    panel->inventoryCallback(h.gui, 0, item);
    const auto details = panel->getSelectionDetails(h.gui);
    expect_true(details.starts_with(item->getLabel()) &&
                    details.find("Quest item - kept for your journey.") < details.find(item->getDescription()),
                "inventory ownership and restrictions must precede long item prose");
}

void testDetailLayoutPreservesLongUtf8TextAndReusesWarmRendering() {
    ManagementHarness h;
    h.gui->applyUiPreferences(R"({"uiScale":100,"textScale":100})");
    std::string text(1023, 'x');
    text += "\xe2\x80\x94";
    for (int index = 0; index < 180; ++index) {
        text += " An account of the relic's history and its former keeper.";
    }
    const std::string suffix = "Final modifier: strength +37";
    text += suffix;
    auto textManager = h.gui->getTextManager();
    const int cappedHeight = textManager->getWrappedTextureSize(text, 440).second;
    DetailViewport::Layout layout;
    expect_true(layout.update(h.gui, text, 440), "the initial full detail text must build a scroll layout");
    expect_true(layout.getContentHeight() > cappedHeight,
                "detail scrolling must extend beyond the renderer's 4096-byte texture limit");
    std::string reconstructed;
    for (const auto &paragraph : layout.getParagraphs()) {
        reconstructed += paragraph.text;
        expect_true(paragraph.text.size() <= 1024 &&
                        (paragraph.text.empty() || (static_cast<unsigned char>(paragraph.text.front()) & 0xc0) != 0x80),
                    "detail chunks must stay bounded without splitting a UTF-8 character");
    }
    expect_true(reconstructed == text && layout.getParagraphs().back().text.ends_with(suffix),
                "the complete detail text and its final modifier must survive chunking");
    const auto viewport = CUtil::rect(0, 0, 440, 120);
    const int bottom = layout.getContentHeight() - viewport->h;
    textManager->clearCache();
    const auto beforeBottomDraw = textManager->getTextureLoadCount();
    layout.draw(h.gui, viewport, bottom);
    expect_true(textManager->getTextureLoadCount() > beforeBottomDraw &&
                    textManager->getTextureLoadCount() <= beforeBottomDraw + 2,
                "jumping to the ending must render only the visible paragraphs");
    const auto warmLoads = textManager->getTextureLoadCount();
    for (int frame = 0; frame < 25; ++frame) {
        expect_true(!layout.update(h.gui, text, 440), "unchanged detail text must retain its measured layout");
        layout.draw(h.gui, viewport, bottom);
    }
    expect_true(textManager->getTextureLoadCount() == warmLoads,
                "warm detail redraws must load zero additional textures");
    expect_true(layout.update(h.gui, text, 320), "changing detail width must invalidate paragraph geometry");
    h.gui->applyUiPreferences(R"({"uiScale":100,"textScale":200})");
    expect_true(layout.update(h.gui, text, 320), "changing text scale must invalidate paragraph geometry");
    expect_true(layout.update(h.gui, "Updated objective\n\nReward received", 320) &&
                    layout.getParagraphs().size() == 3 && layout.getParagraphs()[1].text.empty(),
                "changed details must replace the cached text and retain blank paragraph spacing");
}
} // namespace

int main() {
    SDL_setenv("SDL_VIDEODRIVER", "dummy", 1);
    SDL_setenv("SDL_AUDIODRIVER", "dummy", 1);
    SDL_setenv("SDL_RENDER_DRIVER", "software", 1);
    const char *preferencesPath = "ui-management-test-preferences.json";
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
    testInventoryInspectionNeverConsumesAnItem();
    testEquipmentRequiresAnExplicitActionAndKeepsCurses();
    testCombatInspectionAndUnavailableActionFeedback();
    testCombatLogIsBoundedOrderedAndReadOnly();
    testTradeInspectionAndExactQuantities();
    testCharacterIdentityAndSignedItemDetails();
    testJournalTabsTrackingAndRewardAcknowledgement();
    testDefeatReceiptRecordsActualLossesAfterRecovery();
    testLongRewardReceiptRendersItsFinalItemWithoutGrantingIt();
    testRewardReceiptKeepsMeasuredHeaderAndContinueVisible();
    testCreatureStatusNamesAndDurationsAreInspectable();
    testManagementButtonsExposeAuthoritativeAvailability();
    testCompactCombatantCardsReserveReadableResourceBars();
    testLegacyJournalReflowsWhenOnlyTextScaleChanges();
    testJournalHistoryNavigationUsesTheVisibleDetailPane();
    testJournalTabsPreserveTheirOwnSelectionSearchAndScroll();
    testCharacterModifierInspectionUsesTheActualCompositionSources();
    testWideInventoryPagingStaysAboveTheActionFooter();
    testDetailOverflowKeepsAVisibleCueAndFrontLoadsRestrictions();
    testDetailLayoutPreservesLongUtf8TextAndReusesWarmRendering();
    std::remove(preferencesPath);
    return finish_tests();
}
