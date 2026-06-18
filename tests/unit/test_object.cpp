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

#include "core/CStats.h"
#include "object/CCreature.h"
#include "object/CItem.h"
#include "object/CMarket.h"
#include "object/CPlayer.h"
#include "object/CQuest.h"
#include "test_harness.h"

#include <limits>
#include <memory>
#include <set>

namespace {

std::shared_ptr<CStats> stats_with_main(int stamina, int intelligence, int armor = 0) {
    auto stats = std::make_shared<CStats>();
    stats->setMainStat("intelligence");
    stats->setStamina(stamina);
    stats->setIntelligence(intelligence);
    stats->setArmor(armor);
    return stats;
}

void test_market_guard_paths_and_item_transfers() {
    auto market = std::make_shared<CMarket>();
    auto creature = std::make_shared<CCreature>();
    auto item = std::make_shared<CItem>();
    auto missing_item = std::make_shared<CItem>();

    item->setPower(0);
    creature->setGold(500);

    market->add(nullptr);
    expect_true(market->getItems().empty(), "market should ignore null item additions");
    expect_true(market->getSellCost(nullptr) == 0, "market sell cost should be zero for null items");
    expect_true(market->getBuyCost(nullptr) == 0, "market buy cost should be zero for null items");
    expect_true(!market->sellItem(nullptr, item), "market should reject sales without a creature");
    expect_true(!market->sellItem(creature, nullptr), "market should reject sales without an item");
    expect_true(!market->sellItem(creature, missing_item), "market should reject sales for unstocked items");

    market->setItems({nullptr, item});
    expect_true(market->getItems().size() == 1 && market->getItems().contains(item),
                "market setItems should replace inventory and ignore null entries");
    expect_true(market->sellItem(creature, item), "creature should be able to buy stocked market items");
    expect_true(creature->getGold() == 300, "market sale should charge the creature");
    expect_true(creature->hasInInventory(item), "market sale should move the item to creature inventory");
    expect_true(market->getItems().empty(), "market sale should remove the item from market stock");

    market->buyItem(nullptr, item);
    market->buyItem(creature, nullptr);
    market->buyItem(creature, missing_item);
    expect_true(market->getItems().empty(), "invalid market purchases should not change stock");

    market->buyItem(creature, item);
    expect_true(creature->getGold() == 460, "market purchase should pay the creature");
    expect_true(!creature->hasInInventory(item), "market purchase should remove the item from inventory");
    expect_true(market->getItems().contains(item), "market purchase should move the item into stock");
}

void test_market_prices_are_bounded_and_non_exploitable() {
    auto market = std::make_shared<CMarket>();
    auto buyer = std::make_shared<CCreature>();
    auto seller = std::make_shared<CCreature>();
    auto powerful_item = std::make_shared<CItem>();

    powerful_item->setPower(25);
    market->add(powerful_item);

    expect_true(market->getSellCost(powerful_item) == 100000, "high-power market sale price should be capped");
    expect_true(market->getBuyCost(powerful_item) == 5000, "high-power market buyback should be capped");
    expect_true(market->getBuyCost(powerful_item) <= market->getSellCost(powerful_item),
                "market buyback should never exceed sale price");

    buyer->setGold(99999);
    expect_true(!market->sellItem(buyer, powerful_item), "buyer should not buy a capped item without enough gold");
    expect_true(buyer->getGold() == 99999, "failed capped sale should not change buyer gold");
    expect_true(market->getItems().contains(powerful_item), "failed capped sale should keep item in market");

    buyer->setGold(100000);
    expect_true(market->sellItem(buyer, powerful_item), "buyer should buy capped item at exact price");
    expect_true(buyer->getGold() == 0, "capped sale should subtract exact capped price");
    expect_true(buyer->hasInInventory(powerful_item), "capped sale should transfer item to buyer");

    market->buyItem(buyer, powerful_item);
    expect_true(buyer->getGold() == 5000, "capped buyback should pay the capped buyback price");
    expect_true(!buyer->hasInInventory(powerful_item), "buyback should remove item from seller inventory");
    expect_true(market->getItems().contains(powerful_item), "buyback should return item to market stock");

    market->setSell(-100);
    auto negative_price_item = std::make_shared<CItem>();
    negative_price_item->setPower(1);
    market->add(negative_price_item);
    seller->setGold(1000);
    expect_true(market->getSellCost(negative_price_item) == 0, "negative sale percentages should price at zero");
    expect_true(!market->sellItem(seller, negative_price_item), "zero-priced market sales should fail closed");
    expect_true(seller->getGold() == 1000, "failed zero-priced sale should not change gold");
    expect_true(market->getItems().contains(negative_price_item), "failed zero-priced sale should keep stock");

    market->setBuy(-100);
    seller->addItem(negative_price_item);
    expect_true(market->getBuyCost(negative_price_item) == 0, "negative buyback percentages should price at zero");
    market->buyItem(seller, negative_price_item);
    expect_true(seller->getGold() == 1000, "zero-priced buyback should not pay the seller");
    expect_true(seller->hasInInventory(negative_price_item), "zero-priced buyback should leave item in inventory");

    market->setSell(100);
    auto underflow_item = std::make_shared<CItem>();
    underflow_item->setPower(-2000);
    market->add(underflow_item);
    expect_true(market->getSellCost(underflow_item) == 0, "underflowed sale prices should fail closed");
    expect_true(!market->sellItem(seller, underflow_item), "underflowed zero-price market sales should fail closed");
    expect_true(seller->getGold() == 1000, "underflowed sale should not change gold");
    expect_true(market->getItems().contains(underflow_item), "underflowed sale should keep stock");

    auto low_power_item = std::make_shared<CItem>();
    low_power_item->setPower(-10);
    expect_true(market->getSellCost(low_power_item) == 1, "positive sub-unit sale prices should round up to one");

    auto overflowing_base_item = std::make_shared<CItem>();
    overflowing_base_item->setPower(2048);
    expect_true(market->getSellCost(overflowing_base_item) == 100000, "overflowing base prices should cap safely");

    auto overflowing_scale_item = std::make_shared<CItem>();
    overflowing_scale_item->setPower(1000);
    market->setSell(std::numeric_limits<int>::max());
    expect_true(market->getSellCost(overflowing_scale_item) == 100000, "overflowing scaled prices should cap safely");

    auto replacement_item = std::make_shared<CItem>();
    market->setItems({replacement_item});
    expect_true(market->getItems().size() == 1 && market->getItems().contains(replacement_item),
                "market setItems should remove old stock before adding replacements");
}

void test_player_quest_setters_filter_nulls_and_skip_duplicates() {
    auto player = std::make_shared<CPlayer>();
    auto active = std::make_shared<CQuest>();
    active->setName("activeQuest");
    auto completed = std::make_shared<CQuest>();
    completed->setName("completedQuest");

    player->setQuests({nullptr, active});
    player->setCompletedQuests({nullptr, completed});
    expect_true(player->getQuests().size() == 1 && player->getQuests().contains(active),
                "active quest setter should filter null quests");
    expect_true(player->getCompletedQuests().size() == 1 && player->getCompletedQuests().contains(completed),
                "completed quest setter should filter null quests");

    player->addQuest("activeQuest");
    player->addQuest("completedQuest");
    expect_true(player->getQuests().size() == 1, "adding duplicate active/completed quests should be a no-op");
    expect_true(player->getCompletedQuests().size() == 1, "completed duplicate quest should remain completed only");
}

void test_creature_inventory_equipment_and_ratio_helpers() {
    auto creature = std::make_shared<CCreature>();
    creature->setBaseStats(stats_with_main(10, 10, 200));
    creature->setLevel(0);

    auto inventory_item = std::make_shared<CItem>();
    inventory_item->setTypeId("potion");
    auto equipped_item = std::make_shared<CItem>();
    equipped_item->setTypeId("sword");
    auto null_slot_item = std::shared_ptr<CItem>();

    creature->setItems({nullptr, inventory_item});
    creature->setEquipped({{"0", equipped_item}, {"1", null_slot_item}});
    expect_true(creature->hasInInventory(inventory_item), "creature should track inventory items");
    expect_true(creature->hasEquipped(equipped_item), "creature should find directly equipped items");
    expect_true(creature->hasEquipped([](const auto &item) { return item && item->getTypeId() == "sword"; }),
                "creature should find equipped items with predicates");
    expect_true(creature->hasItem(equipped_item) && creature->hasItem(inventory_item),
                "hasItem should search inventory and equipped slots");
    expect_true(creature->getAllItems().size() == 2, "getAllItems should merge inventory and non-null equipment");
    expect_true(creature->getSlotWithItem(equipped_item) == "0", "creature should locate equipped item slots");
    expect_true(creature->getSlotWithItem(inventory_item) == "-1", "missing equipped items should report no slot");
    expect_true(creature->countItems("potion") == 1, "creature should count matching inventory type ids");

    creature->setHp(999);
    creature->heal(1);
    expect_true(creature->getHp() == 999, "healing should not lower above-maximum hit points");
    expect_true(creature->getHpRatio() == 100, "above-maximum hit points should clamp ratio to 100");
    creature->hurt(-4.0f);
    expect_true(creature->getHp() == 999, "negative floating damage should clamp to zero damage");
    creature->hurt(5);
    expect_true(creature->getHp() == 999, "over-armor damage should clamp to zero damage");

    creature->setMana(999);
    creature->addMana(1);
    expect_true(creature->getMana() == 999, "mana add should not lower above-maximum mana");
    expect_true(creature->getManaRatio() == 100, "above-maximum mana should clamp ratio to 100");
    creature->setMana(-1);
    expect_true(creature->getManaRatio() == 0, "negative mana should clamp ratio to zero");

    auto empty_mana_creature = std::make_shared<CCreature>();
    empty_mana_creature->setBaseStats(stats_with_main(1, 0));
    empty_mana_creature->setMana(1);
    expect_true(empty_mana_creature->getManaRatio() == 100, "zero maximum mana should report a full ratio");

    creature->setGold(25);
    creature->takeGold(5);
    expect_true(creature->getGold() == 20, "takeGold should subtract from creature gold");
}

} // namespace

int main() {
    test_market_guard_paths_and_item_transfers();
    test_market_prices_are_bounded_and_non_exploitable();
    test_player_quest_setters_filter_nulls_and_skip_duplicates();
    test_creature_inventory_equipment_and_ratio_helpers();

    return finish_tests();
}
