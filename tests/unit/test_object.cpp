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
#include "core/CStats.h"
#include "core/CMap.h"
#include "core/CTypes.h"
#include "gui/CAnimation.h"
#include "handler/CTooltipHandler.h"
#include "object/CCreature.h"
#include "object/CCreatureClass.h"
#include "object/CCreatureRace.h"
#include "object/CDialog.h"
#include "object/CEffect.h"
#include "object/CGameObject.h"
#include "object/CInteraction.h"
#include "object/CItem.h"
#include "object/CMapObject.h"
#include "object/CMarket.h"
#include "object/CPlayer.h"
#include "object/CQuest.h"
#include "object/CTile.h"
#include "test_harness.h"
#include "vutil.h"

#include <pybind11/embed.h>

#include <algorithm>
#include <cstdlib>
#include <limits>
#include <map>
#include <memory>
#include <set>
#include <string>
#include <typeindex>
#include <utility>
#include <vector>

namespace {

class PropertyChangeProbe : public CGameObject {
    V_META(PropertyChangeProbe, CGameObject, V_METHOD(PropertyChangeProbe, onPropertyChanged, void, std::string),
           V_METHOD(PropertyChangeProbe, onPropertiesChanged, void, std::set<std::string>))

  public:
    void onPropertyChanged(std::string property_name) { changedProperties.insert(std::move(property_name)); }

    void onPropertiesChanged(std::set<std::string> property_names) {
        changedProperties.insert(property_names.begin(), property_names.end());
    }

    std::set<std::string> changedProperties;
};

using IntIntProbeMap = std::map<int, int>;
using IntStringProbeMap = std::map<int, std::string>;
using StringIntProbeMap = std::map<std::string, int>;
using StringStringProbeMap = std::map<std::string, std::string>;
using IntVectorProbe = std::vector<int>;

class PropertyChangeEmitter : public CGameObject {
    V_META(PropertyChangeEmitter, CGameObject, vstd::meta::empty())

  public:
    void recordChangedProperty(const std::string &property_name) { recordDirectPropertyChanged(property_name); }
};

size_t count_substring(const std::string &haystack, const std::string &needle) {
    if (needle.empty()) {
        return 0;
    }
    size_t count = 0;
    size_t pos = 0;
    while ((pos = haystack.find(needle, pos)) != std::string::npos) {
        ++count;
        pos += needle.size();
    }
    return count;
}

void test_tooltip_handler_builds_labels_descriptions_and_item_bonuses() {
    CTypes::register_type<CGameObject>();
    CTypes::register_type<CMapObject, CGameObject>();
    CTypes::register_type<CItem, CMapObject, CGameObject>();
    CTypes::register_type<CStats, CGameObject>();

    auto plain = std::make_shared<CGameObject>();
    plain->setType("CGameObject");
    plain->setLabel("Ancient Rune");
    plain->setDescription("It hums faintly.");

    auto plain_tooltip = CTooltipHandler::buildTooltip(plain);
    expect_true(plain_tooltip.find("Ancient Rune") != std::string::npos, "tooltip should include the object label");
    expect_true(plain_tooltip.find("It hums faintly.") != std::string::npos,
                "tooltip should include the object description");
    expect_true(plain_tooltip.find("Ancient Rune") < plain_tooltip.find("It hums faintly."),
                "tooltip should list the label before the description");
    expect_true(count_substring(plain_tooltip, "It hums faintly.") == 1,
                "non-item tooltips should include the description exactly once");

    auto item = std::make_shared<CItem>();
    item->setType("CItem");
    item->setLabel("Mossblade");
    item->setDescription("A blade wrapped in moss.");

    auto bonus = std::make_shared<CStats>();
    bonus->setStrength(5);
    bonus->setCrit(-3);
    bonus->setAgility(0);
    item->setBonus(bonus);

    auto item_tooltip = CTooltipHandler::buildTooltip(item);
    expect_true(item_tooltip.find("Mossblade") != std::string::npos, "item tooltip should include the item label");
    expect_true(item_tooltip.find(": 5") != std::string::npos,
                "item tooltip should list positive integer bonuses with their value");
    expect_true(item_tooltip.find("-3") == std::string::npos,
                "item tooltip should hide non-positive bonuses such as negative crit");
    expect_true(count_substring(item_tooltip, "A blade wrapped in moss.") == 1,
                "item tooltips should include the description exactly once after deduplication");
}

void drain_event_loop() {
    auto loop = vstd::event_loop<>::instance();
    for (int i = 0; i < 5; ++i) {
        loop->run();
    }
}

std::shared_ptr<CStats> stats_with_main(int stamina, int intelligence, int armor = 0) {
    auto stats = std::make_shared<CStats>();
    stats->setMainStat("intelligence");
    stats->setStamina(stamina);
    stats->setIntelligence(intelligence);
    stats->setArmor(armor);
    return stats;
}

std::shared_ptr<CGame> game_with_registered_types() {
    auto game = std::make_shared<CGame>();
    for (const auto &[name, builder] : *CTypes::builders()) {
        game->getObjectHandler()->registerType(name, builder);
    }
    return game;
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

void test_creature_direct_setters_notify_property_observers() {
    CTypes::register_type_metadata<PropertyChangeProbe, CGameObject>();

    auto creature = std::make_shared<CCreature>();
    auto probe = std::make_shared<PropertyChangeProbe>();
    auto effect = std::make_shared<CEffect>();
    auto inventory_item = std::make_shared<CItem>();
    auto equipped_item = std::make_shared<CItem>();

    creature->connect("propertyChanged", probe, "onPropertyChanged");
    creature->connect("propertiesChanged", probe, "onPropertiesChanged");

    creature->setAnimation("images/misc/marker");
    creature->setGold(5);
    creature->setHp(12);
    creature->setMana(7);
    creature->setEffects({effect});
    creature->setItems({inventory_item});
    creature->setEquipped({{"0", equipped_item}});

    drain_event_loop();

    expect_true(probe->changedProperties.contains("animation"),
                "direct animation setter should notify property observers");
    expect_true(probe->changedProperties.contains("gold"), "direct gold setter should notify property observers");
    expect_true(probe->changedProperties.contains("hp"), "direct hp setter should notify property observers");
    expect_true(probe->changedProperties.contains("mana"), "direct mana setter should notify property observers");
    expect_true(probe->changedProperties.contains("effects"), "direct effects setter should notify property observers");
    expect_true(probe->changedProperties.contains("items"), "direct inventory setter should notify property observers");
    expect_true(probe->changedProperties.contains("equipped"),
                "direct equipment setter should notify property observers");
}

void test_player_quest_setters_notify_property_observers() {
    CTypes::register_type_metadata<PropertyChangeProbe, CGameObject>();

    auto player = std::make_shared<CPlayer>();
    auto probe = std::make_shared<PropertyChangeProbe>();
    auto active = std::make_shared<CQuest>();
    auto completed = std::make_shared<CQuest>();

    player->connect("propertyChanged", probe, "onPropertyChanged");
    player->connect("propertiesChanged", probe, "onPropertiesChanged");

    player->setQuests({active});
    player->setCompletedQuests({completed});

    drain_event_loop();

    expect_true(probe->changedProperties.contains("quests"),
                "direct active quest setter should notify property observers");
    expect_true(probe->changedProperties.contains("completedQuests"),
                "direct completed quest setter should notify property observers");
}

void test_map_direct_state_setters_notify_property_observers() {
    CTypes::register_type_metadata<PropertyChangeProbe, CGameObject>();

    auto map = std::make_shared<CMap>();
    auto probe = std::make_shared<PropertyChangeProbe>();
    auto tile = std::make_shared<CTile>();
    auto object = std::make_shared<CMapObject>();
    object->setName("observedObject");

    map->connect("propertyChanged", probe, "onPropertyChanged");
    map->connect("propertiesChanged", probe, "onPropertiesChanged");

    map->setTurn(3);
    map->setTiles({tile});
    map->setObjects({object});

    drain_event_loop();

    expect_true(probe->changedProperties.contains("turn"), "direct map turn setter should notify property observers");
    expect_true(probe->changedProperties.contains("tiles"), "direct tile setter should notify property observers");
    expect_true(probe->changedProperties.contains("objects"), "direct object setter should notify property observers");
    expect_true(probe->changedProperties.contains("navigationRevision"),
                "map navigation revision changes should notify property observers");
}

void test_game_object_get_map_prefers_owner_and_falls_back_to_active_map() {
    auto game = std::make_shared<CGame>();
    auto owning_map = std::make_shared<CMap>();
    auto fallback_map = std::make_shared<CMap>();
    owning_map->setGame(game);
    fallback_map->setGame(game);
    game->setMap(owning_map);

    auto map_object = std::make_shared<CMapObject>();
    map_object->setGame(game);
    map_object->setName("ownedObject");
    owning_map->setObjects({map_object});

    auto tile = std::make_shared<CTile>();
    tile->setGame(game);
    tile->setPosx(1);
    tile->setPosy(1);
    tile->setPosz(0);
    owning_map->setTiles({tile});

    auto dialog = std::make_shared<CDialog>();
    auto quest = std::make_shared<CQuest>();
    dialog->setGame(game);
    quest->setGame(game);

    expect_true(map_object->getMap() == owning_map, "map objects should resolve their owning map");
    expect_true(tile->getMap() == owning_map, "tiles should resolve their owning map");
    expect_true(dialog->getMap() == owning_map, "dialogs without an owning map should fall back to the active map");
    expect_true(quest->getMap() == owning_map, "quests without an owning map should fall back to the active map");

    game->setMap(fallback_map);

    expect_true(map_object->getMap() == owning_map, "map objects should keep their owner when the active map changes");
    expect_true(tile->getMap() == owning_map, "tiles should keep their owner when the active map changes");
    expect_true(dialog->getMap() == fallback_map, "dialogs should follow the active map fallback after map changes");
    expect_true(quest->getMap() == fallback_map, "quests should follow the active map fallback after map changes");

    owning_map->setObjects({});
    owning_map->setTiles({});

    expect_true(map_object->getMap() == fallback_map,
                "removed map objects should fall back to the active map after ownership clears");
    expect_true(tile->getMap() == fallback_map,
                "removed tiles should fall back to the active map after ownership clears");
}

void populate_equivalent_value_object(const std::shared_ptr<CGameObject> &object) {
    object->setType("CGameObject");
    object->setName("equivalent");
    object->setProperty("flag", true);
    object->setProperty("count", 7);
    object->setProperty("text", std::string("stable"));
    object->setProperty("probeTags", CTags({CTag::Buff, CTag::Quest}));
    object->setProperty("intSet", std::set<int>({1, 2}));
    object->setProperty("stringSet", std::set<std::string>({"alpha", "beta"}));
    object->setProperty("intToInt", IntIntProbeMap({{1, 10}, {2, 20}}));
    object->setProperty("intToString", IntStringProbeMap({{1, "one"}, {2, "two"}}));
    object->setProperty("stringToInt", StringIntProbeMap({{"one", 1}, {"two", 2}}));
    object->setProperty("stringToString", StringStringProbeMap({{"first", "one"}, {"second", "two"}}));
}

void test_game_object_equivalent_value_covers_supported_property_types() {
    auto left = std::make_shared<CGameObject>();
    auto right = std::make_shared<CGameObject>();
    populate_equivalent_value_object(left);
    populate_equivalent_value_object(right);

    expect_true(CGameObject::equivalentValue(left, right),
                "equivalentValue should compare all supported dynamic primitive property types");

    right->setProperty("stringToString", StringStringProbeMap({{"first", "one"}, {"second", "changed"}}));
    expect_true(!CGameObject::equivalentValue(left, right),
                "equivalentValue should detect supported primitive property changes");

    auto unsupported_left = std::make_shared<CGameObject>();
    auto unsupported_right = std::make_shared<CGameObject>();
    unsupported_left->setProperty("values", IntVectorProbe({1, 2, 3}));
    unsupported_right->setProperty("values", IntVectorProbe({1, 2, 3}));
    expect_true(!CGameObject::equivalentValue(unsupported_left, unsupported_right),
                "equivalentValue should reject unsupported property types");
}

void test_game_object_property_helpers_and_owned_tile_movement() {
    auto object = std::make_shared<CGameObject>();
    expect_true(object->getStringProperty("missing").empty(), "missing string properties should default empty");
    expect_true(!object->getBoolProperty("missing"), "missing bool properties should default false");
    expect_true(object->getNumericProperty("missing") == 0, "missing numeric properties should default zero");

    object->setType("HelperProbe");
    object->setName("object");
    object->setStringProperty("label", "visible");
    object->setBoolProperty("enabled", true);
    object->setNumericProperty("counter", 2);
    object->incProperty("counter", 3);
    object->addTag("quest");
    object->addTag(CTag::Buff);
    object->removeTag("quest");

    expect_true(object->to_string() == "HelperProbe:object", "to_string should combine type and name");
    expect_true(object->getStringProperty("label") == "visible", "string property helper should read static values");
    expect_true(object->getBoolProperty("enabled"), "bool property helper should read dynamic values");
    expect_true(object->getNumericProperty("counter") == 5, "numeric increment helper should update dynamic values");
    expect_true(!object->hasTag("quest") && object->hasTag(CTag::Buff),
                "string and enum tag helpers should update the tag set");
    expect_true(!object->getGraphicsObject(), "objects without a game should not create graphics objects");

    auto probe = std::make_shared<PropertyChangeProbe>();
    object->connect("propertyChanged", probe, "onPropertyChanged");
    object->connect("propertiesChanged", probe, "onPropertiesChanged");
    object->notifyPropertyChanged("manual");
    object->notifyPropertiesChanged({});
    object->notifyPropertiesChanged({"bulk", "manual"});
    object->disconnect("propertyChanged", probe, "onPropertyChanged");
    object->notifyPropertyChanged("ignored");

    drain_event_loop();

    expect_true(probe->changedProperties.contains("manual") && probe->changedProperties.contains("bulk") &&
                    !probe->changedProperties.contains("ignored"),
                "manual notifications should emit non-empty property signals and honor disconnects");

    auto map = std::make_shared<CMap>();
    auto tile = std::make_shared<CTile>();
    tile->setPosx(1);
    tile->setPosy(1);
    tile->setPosz(0);
    map->setTiles({tile});

    tile->move(2, 3, 0);
    expect_true(tile->getCoords() == Coords(3, 4, 0), "owned tiles should move through their owning map");
    expect_true(map->getTile(3, 4, 0) == tile, "tile movement should update the owning map coordinate index");

    tile->moveTo(1, 1, 0);
    expect_true(tile->getCoords() == Coords(1, 1, 0), "moveTo should target absolute tile coordinates");

    auto standalone_tile = std::make_shared<CTile>();
    standalone_tile->setMovementCost(0);
    expect_true(standalone_tile->getMovementCost() == 1, "tile movement cost should clamp to at least one");
    standalone_tile->setMovementCost(4);
    expect_true(standalone_tile->getMovementCost() == 4, "tile movement cost should keep valid positive values");
    standalone_tile->setPosx(5);
    standalone_tile->setPosy(6);
    standalone_tile->setPosz(7);
    expect_true(standalone_tile->getCoords() == Coords(5, 6, 7),
                "public tile coordinate setters should update all tile coordinates");
}

void test_animation_property_events_invalidate_cached_graphics_object() {
    auto game = game_with_registered_types();
    auto object = std::make_shared<PropertyChangeEmitter>();
    object->setGame(game);
    object->setAnimation("images/item");

    auto static_animation = object->getGraphicsObject();
    expect_true(static_animation && static_animation->meta()->inherits("CStaticAnimation"),
                "initial graphics object should use the static animation source");

    object->recordChangedProperty("label");
    auto after_unrelated_property = object->getGraphicsObject();
    expect_true(after_unrelated_property == static_animation,
                "unrelated property events should not invalidate the cached graphics object");

    object->notifyPropertyChanged("label");
    auto after_unrelated_notification = object->getGraphicsObject();
    expect_true(after_unrelated_notification == static_animation,
                "unrelated property notifications should not invalidate the cached graphics object");

    object->recordChangedProperty("animation");
    auto after_animation_event = object->getGraphicsObject();
    expect_true(after_animation_event && after_animation_event != static_animation,
                "animation property events should invalidate the cached graphics object");
    expect_true(after_animation_event && after_animation_event->meta()->inherits("CStaticAnimation"),
                "animation property event refresh should keep using the current animation source");

    object->notifyPropertiesChanged({"label"});
    auto after_unrelated_notification_batch = object->getGraphicsObject();
    expect_true(after_unrelated_notification_batch == after_animation_event,
                "unrelated property notification batches should not invalidate the cached graphics object");

    object->notifyPropertiesChanged({"animation", "label"});
    auto after_animation_notification_batch = object->getGraphicsObject();
    expect_true(after_animation_notification_batch && after_animation_notification_batch != after_animation_event,
                "animation property notification batches should invalidate the cached graphics object");

    object->setAnimation("images/monsters/octobogz");
    auto dynamic_animation = object->getGraphicsObject();
    expect_true(dynamic_animation && dynamic_animation != after_animation_notification_batch,
                "changing animation should rebuild the cached graphics object");
    expect_true(dynamic_animation && dynamic_animation->meta()->inherits("CDynamicAnimation"),
                "rebuilt graphics object should use the updated animation source");
}

void test_creature_inventory_equipment_and_ratio_helpers() {
    auto creature = std::make_shared<CCreature>();
    creature->setBaseStats(stats_with_main(10, 10, 200));
    creature->setLevel(0);

    auto inventory_item = std::make_shared<CItem>();
    inventory_item->setTypeId("potion");
    auto same_type_inventory_item = std::make_shared<CItem>();
    same_type_inventory_item->setTypeId("potion");
    auto equipped_item = std::make_shared<CItem>();
    equipped_item->setTypeId("sword");
    auto same_type_equipped_item = std::make_shared<CItem>();
    same_type_equipped_item->setTypeId("sword");
    auto null_slot_item = std::shared_ptr<CItem>();

    creature->setItems({nullptr, inventory_item});
    creature->setEquipped({{"0", equipped_item}, {"1", null_slot_item}});
    expect_true(creature->hasInInventory(inventory_item), "creature should track inventory items");
    expect_true(!creature->hasInInventory(same_type_inventory_item),
                "creature inventory identity should not collapse matching configured item ids");
    expect_true(creature->hasEquipped(equipped_item), "creature should find directly equipped items");
    expect_true(!creature->hasEquipped(same_type_equipped_item),
                "creature equipment identity should not collapse matching configured item ids");
    expect_true(creature->hasEquipped([](const auto &item) { return item && item->getTypeId() == "sword"; }),
                "creature should find equipped items with predicates");
    expect_true(creature->hasItem(equipped_item) && creature->hasItem(inventory_item),
                "hasItem should search inventory and equipped slots");
    expect_true(creature->getAllItems().size() == 2, "getAllItems should merge inventory and non-null equipment");
    expect_true(creature->getSlotWithItem(equipped_item) == "0", "creature should locate equipped item slots");
    expect_true(creature->getSlotWithItem(same_type_equipped_item) == "-1",
                "creature slot lookup should require the exact equipped item instance");
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

void test_no_archetype_creature_stats_keep_legacy_composition() {
    // Regression guard (EPIC_03/STORY_01/SUBSTORY_01): a creature with NO race/creatureClass
    // archetype must keep the legacy stat composition computed in CCreature::getStats():
    //   mainStat  = baseStats.mainStat
    //   numerics  = baseStats + level * levelStats + sum(equipped item bonuses) + sum(effect bonuses)
    // Since no archetype types exist yet, every creature is "no-archetype"; this captures today's
    // behaviour as the legacy baseline and fails with a per-property diff if that composition changes.
    auto creature = std::make_shared<CCreature>();

    auto base = std::make_shared<CStats>();
    base->setMainStat("intelligence");
    base->setStrength(10);
    base->setAgility(4);
    base->setStamina(7);
    base->setIntelligence(12);
    base->setArmor(3);
    base->setBlock(2);
    base->setDmgMin(5);
    base->setDmgMax(9);
    base->setAttack(6);
    base->setHit(11);
    base->setCrit(1);
    base->setFireResist(8);
    base->setFrostResist(0);
    base->setNormalResist(2);
    base->setThunderResist(4);
    base->setShadowResist(6);
    base->setDamage(13);
    creature->setBaseStats(base);

    auto level_stats = std::make_shared<CStats>();
    level_stats->setStrength(2);
    level_stats->setAgility(1);
    level_stats->setStamina(3);
    level_stats->setIntelligence(1);
    level_stats->setArmor(1);
    level_stats->setHit(1);
    level_stats->setDamage(2);
    creature->setLevelStats(level_stats);

    const int level = 3;
    creature->setLevel(level);

    auto weapon_bonus = std::make_shared<CStats>();
    weapon_bonus->setStrength(4);
    weapon_bonus->setDmgMin(2);
    weapon_bonus->setDmgMax(3);
    weapon_bonus->setCrit(5);
    auto weapon = std::make_shared<CItem>();
    weapon->setBonus(weapon_bonus);

    auto armor_bonus = std::make_shared<CStats>();
    armor_bonus->setArmor(7);
    armor_bonus->setBlock(3);
    armor_bonus->setFrostResist(2);
    auto armor_item = std::make_shared<CItem>();
    armor_item->setBonus(armor_bonus);

    auto empty_slot_item = std::shared_ptr<CItem>();
    creature->setEquipped({{"0", weapon}, {"1", armor_item}, {"2", empty_slot_item}});

    auto effect_bonus = std::make_shared<CStats>();
    effect_bonus->setAgility(5);
    effect_bonus->setHit(4);
    effect_bonus->setShadowResist(1);
    auto effect = std::make_shared<CEffect>();
    effect->setBonus(effect_bonus);
    creature->setEffects({effect});

    // Independently recompute the expected legacy composition.
    auto expected = std::make_shared<CStats>();
    expected->setMainStat(base->getMainStat());
    expected->addBonus(base);
    for (int i = 0; i < level; ++i) {
        expected->addBonus(level_stats);
    }
    expected->addBonus(weapon_bonus);
    expected->addBonus(armor_bonus);
    expected->addBonus(effect_bonus);

    auto actual = creature->getStats();

    expect_true(actual->getMainStat() == expected->getMainStat(),
                "no-archetype creature getStats should keep baseStats mainStat");

    actual->meta()->for_all_properties(actual, [&](auto property) {
        if (property->value_type() != std::type_index(typeid(int))) {
            return;
        }
        int actual_value = actual->getProperty<int>(property->name());
        int expected_value = expected->getProperty<int>(property->name());
        if (actual_value != expected_value) {
            std::cerr << "STAT DIFF [" << property->name() << "] expected " << expected_value << " but got "
                      << actual_value << "\n";
        }
        expect_true(actual_value == expected_value,
                    "no-archetype creature getStats should match legacy baseStats + level*levelStats + "
                    "equipment + effects composition");
    });
}

void test_creature_stat_precedence_orders_sources_and_main_stat() {
    // Pins the approved creature stat precedence contract
    // (docs/design/creature_archetypes.md, "Creature stat precedence contract"):
    // effective stats compose, least- to most-specific, as
    //   race.baseStats -> creatureClass.baseStats -> creature.baseStats ->
    //   creatureClass.levelStats (per level) -> creature.levelStats (per level) ->
    //   equipment -> effects,
    // and the composed mainStat is taken from creatureClass.baseStats first, falling
    // back to legacy creature.baseStats when no class is present. The race /
    // creatureClass archetype objects do not exist yet, so this pins the currently
    // implemented portion (positions 3, 5, 6, 7) and the legacy main-stat fallback.
    auto creature = std::make_shared<CCreature>();

    // Each currently-implemented source contributes to the SAME property (intelligence)
    // so the test proves every later source is layered on top of (does not discard) the
    // earlier ones, in the documented order.
    auto base = std::make_shared<CStats>();
    base->setMainStat("intelligence"); // legacy creature.baseStats mainStat -> the fallback
    base->setIntelligence(10);         // 3. creature.baseStats
    creature->setBaseStats(base);

    auto level_stats = std::make_shared<CStats>();
    level_stats->setIntelligence(2); // 5. creature.levelStats, applied once per level
    creature->setLevelStats(level_stats);

    const int level = 3;
    creature->setLevel(level);

    auto equip_bonus = std::make_shared<CStats>();
    equip_bonus->setIntelligence(5); // 6. equipment
    auto item = std::make_shared<CItem>();
    item->setBonus(equip_bonus);
    creature->setEquipped({{"0", item}});

    auto effect_bonus = std::make_shared<CStats>();
    effect_bonus->setIntelligence(7); // 7. effects (most specific implemented source)
    auto effect = std::make_shared<CEffect>();
    effect->setBonus(effect_bonus);
    creature->setEffects({effect});

    auto stats = creature->getStats();

    // Each source is layered in order, so the composed value is the running total of
    // every documented stage; dropping or reordering any stage changes this number.
    const int expected_intelligence = 10 /*base*/ + level * 2 /*levelStats*/ + 5 /*equip*/ + 7 /*effects*/;
    expect_true(stats->getIntelligence() == expected_intelligence,
                "stat precedence should layer base + level*levelStats + equipment + effects in order");

    // Main stat is selected (not accumulated): with no creatureClass it falls back to
    // the legacy creature.baseStats mainStat, and getMainValue reads it from the fully
    // composed block.
    expect_true(stats->getMainStat() == "intelligence",
                "composed main stat should fall back to legacy creature baseStats when no class is present");
    expect_true(stats->getMainValue() == expected_intelligence,
                "main value should read the selected main stat out of the fully composed stat block");

    // Sanity: dropping the most-specific implemented source (effects) must lower the
    // result, proving effects really are part of the composed order (last wins on top).
    creature->setEffects({});
    expect_true(creature->getStats()->getIntelligence() == expected_intelligence - 7,
                "removing the effects source should remove exactly its contribution from the composed stat");
}

void test_creature_class_main_stat_is_authoritative_over_race() {
    // [EPIC_02][STORY_04][SUBSTORY_03] Make creatureClass authoritative for mainStat.
    // When a creature has a composed creatureClass declaring a main stat, that class main stat
    // is AUTHORITATIVE for the composed block (buildLegacyStats selects -- not accumulates --
    // mainStat), overriding the legacy/race creature.baseStats main stat. A creature with no
    // class, or a class with an empty main stat, falls back to the legacy base main stat
    // exactly, so the no-archetype path is unchanged.
    auto creature = std::make_shared<CCreature>();

    // Legacy/race base declares a CONFLICTING main stat (strength) with distinct numeric
    // values so the selected stat is observable through getMainValue().
    auto base = std::make_shared<CStats>();
    base->setMainStat("strength");
    base->setStrength(3);
    base->setIntelligence(11);
    creature->setBaseStats(base);

    // No class: composed main stat falls back to the legacy base main stat.
    expect_true(creature->getStats()->getMainStat() == "strength",
                "with no creatureClass the composed main stat falls back to the legacy base main stat");
    expect_true(creature->getStats()->getMainValue() == 3, "the legacy fallback main value reads strength (3)");

    // Attach a creatureClass declaring intelligence as its main stat: class wins.
    auto klass = std::make_shared<CCreatureClass>();
    klass->setMainStat("intelligence");
    creature->setCreatureClass(klass);

    auto composed = creature->getStats();
    expect_true(composed->getMainStat() == "intelligence",
                "creatureClass main stat is authoritative over the conflicting legacy/race main stat");
    expect_true(composed->getMainValue() == 11,
                "the composed main value reads the class-selected stat (intelligence=11)");
    expect_true(creature->getManaMax() == 11 * 7,
                "mana max derives from the class-authoritative main stat (getMainValue*7)");

    // A class that declares no main stat must not override the legacy fallback.
    auto emptyClass = std::make_shared<CCreatureClass>();
    creature->setCreatureClass(emptyClass);
    expect_true(creature->getStats()->getMainStat() == "strength",
                "a creatureClass with an empty main stat preserves the legacy base main stat");

    // Clearing the class restores the no-archetype legacy path exactly.
    creature->setCreatureClass(nullptr);
    expect_true(creature->getStats()->getMainStat() == "strength",
                "clearing the creatureClass restores the legacy no-archetype main stat selection");
}

void test_creature_archetype_identity_accessors_use_fallbacks() {
    auto creature = std::make_shared<CCreature>();

    creature->setTypeId("Pritz");
    creature->setName("pritz_instance_1");
    creature->setLabel("Pritz Footsoldier");
    expect_true(creature->getArchetypeRaceId() == "Pritz", "archetype race id should prefer the configured type id");
    expect_true(creature->getArchetypeClassId() == "Pritz", "archetype class id should prefer the configured type id");
    expect_true(creature->getArchetypeRaceLabel() == "Pritz Footsoldier",
                "archetype race label should prefer the configured label");
    expect_true(creature->getArchetypeClassLabel() == "Pritz Footsoldier",
                "archetype class label should prefer the configured label");

    auto without_type = std::make_shared<CCreature>();
    without_type->setName("nameless_horror");
    without_type->setLabel("Nameless Horror");
    expect_true(without_type->getArchetypeRaceId() == "nameless_horror",
                "archetype race id should fall back to name when type id is empty");
    expect_true(without_type->getArchetypeClassId() == "nameless_horror",
                "archetype class id should fall back to name when type id is empty");
    expect_true(without_type->getArchetypeRaceLabel() == "Nameless Horror",
                "archetype race label should prefer label even without a type id");
    expect_true(without_type->getArchetypeClassLabel() == "Nameless Horror",
                "archetype class label should prefer label even without a type id");

    auto identity_only = std::make_shared<CCreature>();
    identity_only->setTypeId("Gooby");
    identity_only->setName("the_dreaded_gooby");
    expect_true(identity_only->getArchetypeRaceLabel() == "Gooby",
                "archetype race label should fall back to archetype race id when label is empty");
    expect_true(identity_only->getArchetypeClassLabel() == "Gooby",
                "archetype class label should fall back to archetype class id when label is empty");

    auto bare = std::make_shared<CCreature>();
    bare->setName("lonely_actor");
    expect_true(bare->getArchetypeRaceLabel() == "lonely_actor",
                "archetype race label should fall back through archetype race id to name when nothing else is set");
    expect_true(bare->getArchetypeClassLabel() == "lonely_actor",
                "archetype class label should fall back through archetype class id to name when nothing else is set");
}

void test_creature_effective_interactions_compose_and_dedupe_sources() {
    auto creature = std::make_shared<CCreature>();
    creature->setLevel(2);

    // Innate / class action exposed through a levelling unlock at level 1.
    auto innate_strike = std::make_shared<CInteraction>();
    innate_strike->setTypeId("strike");
    innate_strike->setName("levelling-strike");

    // A levelling unlock gated to a higher level than the creature has reached.
    auto future_unlock = std::make_shared<CInteraction>();
    future_unlock->setTypeId("ultimate");
    future_unlock->setName("levelling-ultimate");

    // A levelling unlock keyed by name only (no typeId) at an unlocked level.
    auto named_unlock = std::make_shared<CInteraction>();
    named_unlock->setName("ward");

    CInteractionMap levelling;
    levelling["1"] = innate_strike;
    levelling["5"] = future_unlock;
    levelling["2"] = named_unlock;
    creature->setLevelling(levelling);

    // Concrete action overriding the innate "strike" (same typeId, different
    // instance) plus a unique concrete action.
    auto concrete_strike = std::make_shared<CInteraction>();
    concrete_strike->setTypeId("strike");
    concrete_strike->setName("concrete-strike");
    creature->addAction(concrete_strike);

    auto unique_action = std::make_shared<CInteraction>();
    unique_action->setTypeId("dash");
    unique_action->setName("concrete-dash");
    creature->addAction(unique_action);

    auto effective = creature->getEffectiveInteractions();

    auto contains = [&effective](const std::shared_ptr<CInteraction> &action) {
        return effective.find(action) != effective.end();
    };
    auto count_with_type = [&effective](const std::string &typeId) {
        return std::count_if(effective.begin(), effective.end(),
                             [&typeId](const auto &action) { return action && action->getTypeId() == typeId; });
    };

    expect_true(effective.size() == 3, "effective interactions should expose strike, ward and dash exactly once each");
    expect_true(count_with_type("strike") == 1,
                "a typeId duplicated across innate and concrete sources should appear only once");
    expect_true(contains(concrete_strike) && !contains(innate_strike),
                "concrete actions should override duplicate innate/level-unlocked actions of the same typeId");
    expect_true(contains(unique_action), "unique concrete actions should be present in the effective interaction set");
    expect_true(contains(named_unlock),
                "level-unlocked actions at or below the current level should be exposed (name-keyed dedupe)");
    expect_true(!contains(future_unlock), "level unlocks above the current level should not yet be exposed");

    // getInteractions() delegates to the composed, de-duplicated set.
    expect_true(creature->getInteractions() == effective,
                "getInteractions should delegate to the effective, de-duplicated interaction set");
}
void test_creature_effective_interactions_compose_archetype_sources() {
    // Pins that getEffectiveInteractions folds the race/class archetype sources
    // into the composed set at the documented precedence positions
    // (docs/design/creature_archetypes.md, "Creature action merge contract"):
    //   1. race innate -> 2. class starting -> 3. class level unlocks ->
    //   4. concrete template (own levelling then own actions), most-specific wins.
    auto interaction = [](const std::string &typeId, const std::string &name) {
        auto action = std::make_shared<CInteraction>();
        action->setType("CInteraction");
        action->setTypeId(typeId);
        action->setName(name);
        return action;
    };

    auto creature = std::make_shared<CCreature>();
    creature->setLevel(2);

    // (1) race innate: a generic Attack and a race-only ability.
    auto raceAttack = interaction("Attack", "raceAttack");
    auto raceClaw = interaction("Claw", "raceClaw");
    auto race = std::make_shared<CCreatureRace>();
    race->setActions({raceAttack, raceClaw});
    creature->setRace(race);

    // (2) class starting: a duplicate Attack overriding the race's Attack.
    auto classAttack = interaction("Attack", "classAttack");
    // (3) class level unlocks: one unlocked at the current level, one gated above it.
    auto classStrike = interaction("Strike", "classStrike");
    auto classUltimate = interaction("Ultimate", "classUltimate");
    auto klass = std::make_shared<CCreatureClass>();
    klass->setActions({classAttack});
    CInteractionMap classLevelling;
    classLevelling["1"] = classStrike;
    classLevelling["5"] = classUltimate;
    klass->setLevelling(classLevelling);
    creature->setCreatureClass(klass);

    // (4) concrete template: the most specific Attack override plus a unique action.
    auto concreteAttack = interaction("Attack", "concreteAttack");
    auto concreteFinisher = interaction("Finisher", "concreteFinisher");
    creature->addAction(concreteAttack);
    creature->addAction(concreteFinisher);

    auto effective = creature->getEffectiveInteractions();
    auto contains = [&effective](const std::shared_ptr<CInteraction> &action) {
        return effective.find(action) != effective.end();
    };
    auto count_with_type = [&effective](const std::string &typeId) {
        return std::count_if(effective.begin(), effective.end(),
                             [&typeId](const auto &action) { return action && action->getTypeId() == typeId; });
    };

    // Attack is defined by race, class and concrete sources; only the concrete
    // (most-specific) definition survives, exactly once.
    expect_true(count_with_type("Attack") == 1,
                "Attack duplicated across race/class/concrete should collapse to one entry");
    expect_true(contains(concreteAttack) && !contains(raceAttack) && !contains(classAttack),
                "the concrete Attack should win over the race and class definitions");
    // Unique actions from every source are preserved.
    expect_true(contains(raceClaw), "race innate actions should be exposed in the composed set");
    expect_true(contains(classStrike), "class level unlocks at/below current level should be exposed");
    expect_true(contains(concreteFinisher), "unique concrete actions should be exposed");
    // The class level unlock gated above the current level is withheld.
    expect_true(!contains(classUltimate), "class level unlocks above the current level should not be exposed");
    expect_true(effective.size() == 4, "composed set should be Attack (concrete) + Claw + Strike + Finisher");

    // Legacy creature (no race, no class) still composes only its own sources.
    auto legacy = std::make_shared<CCreature>();
    legacy->addAction(interaction("Attack", "legacyAttack"));
    auto legacyEffective = legacy->getEffectiveInteractions();
    expect_true(legacyEffective.size() == 1, "a creature with no race/class should compose only its own actions");
}
void test_creature_action_merge_dedupes_by_type_id() {
    // Pins the approved creature action merge contract
    // (docs/design/creature_archetypes.md, "Creature action merge contract"):
    // actions are composed in precedence order (race innate -> class starting ->
    // class level unlocks -> concrete template) and deduplicated by `typeId`
    // (falling back to `name` only when `typeId` is empty), last/most-specific wins.
    auto creature = std::make_shared<CCreature>();

    auto interaction = [](const std::string &typeId, const std::string &name) {
        auto action = std::make_shared<CInteraction>();
        action->setType("CInteraction");
        action->setTypeId(typeId);
        action->setName(name);
        return action;
    };

    // (1) race innate: a generic Attack and a race-only ability.
    auto raceAttack = interaction("Attack", "raceAttack");
    auto raceClaw = interaction("Claw", "raceClaw");
    // (2) class starting: a duplicate Attack (same typeId, different instance/name).
    auto classAttack = interaction("Attack", "classAttack");
    // (3) class level unlock: a unique unlock.
    auto levelStrike = interaction("Strike", "levelStrike");
    // (4) concrete template: the most specific Attack override plus a unique action.
    auto concreteAttack = interaction("Attack", "concreteAttack");
    auto concreteFinisher = interaction("Finisher", "concreteFinisher");

    creature->addAction(raceAttack);
    creature->addAction(raceClaw);
    creature->addAction(classAttack);
    creature->addAction(levelStrike);
    creature->addAction(concreteAttack);
    creature->addAction(concreteFinisher);

    const auto actions = creature->getActions();

    auto withTypeId = [&actions](const std::string &typeId) {
        std::vector<std::shared_ptr<CInteraction>> matches;
        for (const auto &action : actions) {
            if (action && action->getTypeId() == typeId) {
                matches.push_back(action);
            }
        }
        return matches;
    };

    expect_true(withTypeId("Attack").size() == 1,
                "duplicate Attack actions from race/class/concrete sources should collapse to a single entry");
    expect_true(!withTypeId("Attack").empty() && withTypeId("Attack").front() == concreteAttack,
                "the last/most-specific source should win for a deduplicated action typeId");
    expect_true(actions.contains(raceClaw) && actions.contains(levelStrike) && actions.contains(concreteFinisher),
                "unique actions from each source should be preserved through the merge");
    expect_true(!actions.contains(raceAttack) && !actions.contains(classAttack),
                "earlier Attack definitions should be replaced by the more specific source");
    expect_true(actions.size() == 4, "the merged action set should keep one Attack plus the three unique actions");

    // Re-adding the exact same instance is idempotent and does not duplicate.
    creature->addAction(concreteAttack);
    expect_true(creature->getActions().size() == 4, "re-adding the same action instance should be idempotent");

    // typeId-empty actions fall back to name for dedupe.
    auto namedCreature = std::make_shared<CCreature>();
    auto firstWander = interaction("", "Wander");
    auto secondWander = interaction("", "Wander");
    auto patrol = interaction("", "Patrol");
    namedCreature->addAction(firstWander);
    namedCreature->addAction(secondWander);
    namedCreature->addAction(patrol);
    const auto namedActions = namedCreature->getActions();
    expect_true(namedActions.size() == 2,
                "actions without a typeId should deduplicate by name (last wins) and keep distinct names");
    expect_true(namedActions.contains(secondWander) && !namedActions.contains(firstWander),
                "the later name-keyed action should replace the earlier one when typeId is empty");
}

void test_creature_duplicate_attack_from_race_and_class_collapses_to_single_identity() {
    // [EPIC_02][STORY_05][SUBSTORY_02] Deduplicate actions by stable identity.
    // Required validation: a duplicated `Attack` configured in BOTH the race
    // source and the class source must collapse to a single effective action of
    // stable identity (typeId, falling back to name), with the most-specific
    // source winning -- not two `Attack` entries accumulating from the overlap.
    //
    // Race / class actions funnel into the creature through the approved merge
    // primitive `CCreature::addAction` (docs/design/creature_archetypes.md,
    // "Creature action merge contract": setActions composes the set by calling
    // addAction per entry, applied least-specific -> most-specific). The
    // composed, de-duplicated set is exposed via getEffectiveInteractions().
    auto creature = std::make_shared<CCreature>();

    auto interaction = [](const std::string &typeId, const std::string &name) {
        auto action = std::make_shared<CInteraction>();
        action->setType("CInteraction");
        action->setTypeId(typeId);
        action->setName(name);
        return action;
    };

    // (1) Race source: an innate Attack plus a race-only ability.
    auto raceAttack = interaction("Attack", "raceAttack");
    auto raceClaw = interaction("Claw", "raceClaw");
    // (2) Class source: a duplicate Attack (same typeId, different instance).
    auto classAttack = interaction("Attack", "classAttack");

    // Compose least-specific -> most-specific, exactly as setActions would when
    // merging race then class sources.
    creature->addAction(raceAttack);
    creature->addAction(raceClaw);
    creature->addAction(classAttack);

    auto countTypeId = [](const std::set<std::shared_ptr<CInteraction>> &set, const std::string &typeId) {
        return std::count_if(set.begin(), set.end(),
                             [&typeId](const auto &action) { return action && action->getTypeId() == typeId; });
    };

    // Stored action set: one Attack (class wins) plus the unique race Claw.
    const auto actions = creature->getActions();
    expect_true(countTypeId(actions, "Attack") == 1,
                "an Attack duplicated across race and class sources must collapse to a single entry");
    expect_true(actions.contains(classAttack) && !actions.contains(raceAttack),
                "the more-specific class Attack should win over the race Attack of the same typeId");
    expect_true(actions.contains(raceClaw), "a unique race-only action should survive the merge");
    expect_true(actions.size() == 2, "the merged set should hold exactly one Attack plus the unique Claw");

    // Effective interaction set exposes the same single-identity, deterministic
    // composition.
    const auto effective = creature->getEffectiveInteractions();
    expect_true(countTypeId(effective, "Attack") == 1,
                "the effective interaction set must expose the deduplicated Attack exactly once");
    expect_true(effective.find(classAttack) != effective.end() && effective.find(raceAttack) == effective.end(),
                "getEffectiveInteractions should keep the most-specific Attack identity");
    expect_true(effective.size() == 2, "the effective interaction set should contain no duplicate action identity");
}

void test_no_archetype_creature_level_up_mutates_actions_via_levelling() {
    // Regression guard (EPIC_03/STORY_01/SUBSTORY_02): a legacy creature with NO race/creatureClass
    // archetype must keep the existing level-up action mutation. CCreature::levelUp()
    // (src/object/CCreature.cpp) increments the level and then calls addAction(getLevelAction());
    // getLevelAction() looks the new level up in the `levelling` map and clones the configured
    // action through the object handler, and addAction inserts it into the creature's MUTABLE
    // `actions` set exposed by getActions(). This captures that behaviour as today's baseline:
    // levelling unlocks land in the actions set on level-up. It fails if that mutation regresses.

    // getLevelAction() round-trips the configured action through the object handler's clone()
    // (serialize -> deserialize), so the handler must know how to construct a CInteraction (and the
    // CEffect it can reference). Register the types the same way the proven configured-object clone
    // coverage in this file does, then build the unlock templates through the handler so they clone
    // cleanly -- a bare make_shared<CInteraction> is not wired into the type system for cloning.
    CTypes::register_type<CGameObject>();
    CTypes::register_type<CEffect, CGameObject>();
    CTypes::register_type<CInteraction, CGameObject>();
    auto game = std::make_shared<CGame>();
    game->getObjectHandler()->registerType("CGameObject", []() { return std::make_shared<CGameObject>(); });
    game->getObjectHandler()->registerType("CEffect", []() { return std::make_shared<CEffect>(); });
    game->getObjectHandler()->registerType("CInteraction", []() { return std::make_shared<CInteraction>(); });

    auto makeUnlock = [&](const std::string &typeId, const std::string &name) {
        auto config = std::make_shared<json>();
        (*config)["class"] = "CInteraction";
        (*config)["properties"]["typeId"] = typeId;
        (*config)["properties"]["name"] = name;
        game->getObjectHandler()->registerConfig(typeId, config);
        return game->createObject<CInteraction>(typeId);
    };

    auto creature = std::make_shared<CCreature>();
    creature->setGame(game);

    // Minimal stats so the heal(0)/addMana(0) calls inside levelUp() have a sane max to clamp to.
    auto base = std::make_shared<CStats>();
    base->setMainStat("intelligence");
    base->setStamina(7);
    base->setIntelligence(12);
    creature->setBaseStats(base);
    creature->setLevelStats(std::make_shared<CStats>());

    // Legacy levelling map: an action configured to unlock at level 1, and one gated behind a
    // higher level that must NOT leak into the actions set on the first level-up.
    auto strike = makeUnlock("levelStrike", "level-one-strike");
    auto ultimate = makeUnlock("levelUltimate", "level-five-ultimate");
    expect_true(static_cast<bool>(strike) && static_cast<bool>(ultimate),
                "test setup should build the levelling unlock templates through the object handler");

    CInteractionMap levelling;
    levelling["1"] = strike;
    levelling["5"] = ultimate;
    creature->setLevelling(levelling);

    expect_true(creature->getActions().empty(),
                "a freshly constructed legacy creature should start with no concrete actions");

    // level 0 -> 1: drive the level-up through the public experience path. levelUp() is protected,
    // so we exercise it the way gameplay does: addExp() loops levelUp() while exp reaches
    // getExpForNextLevel(). A freshly constructed creature is dead (hp 0), and addExp() early-returns
    // when !isAlive(), so make it alive first. At level 0 getExpForNextLevel() == getExpForLevel(1)
    // == 0, so a single addExp(0) advances exactly one level (0 -> 1) without granting the level-5
    // unlock.
    creature->setHp(10);
    creature->addExp(0);
    expect_true(creature->getLevel() == 1, "levelling should advance a legacy creature's level");

    const auto afterFirst = creature->getActions();
    auto hasTypeId = [](const std::set<std::shared_ptr<CInteraction>> &actions, const std::string &typeId) {
        return std::any_of(actions.begin(), actions.end(),
                           [&typeId](const auto &action) { return action && action->getTypeId() == typeId; });
    };

    expect_true(afterFirst.size() == 1,
                "leveling a legacy creature to level 1 should insert exactly the level-1 levelling action");
    expect_true(hasTypeId(afterFirst, "levelStrike"),
                "levelUp should insert the level-1 levelling unlock into the legacy creature's mutable actions set");
    expect_true(!hasTypeId(afterFirst, "levelUltimate"),
                "levelUp should not insert a levelling unlock gated above the creature's current level");

    // The action stored in the set is a clone, not the configured template instance, mirroring how
    // getLevelAction() clones through the object handler today.
    expect_true(afterFirst.find(strike) == afterFirst.end(),
                "the inserted action should be a clone of the levelling template, not the template instance");
}

void test_game_object_comparator_and_identity_sets_document_current_semantics() {
    std::shared_ptr<CGameObject> null_object;
    auto object = std::make_shared<CGameObject>();

    expect_true(CGameObject::name_comparator(null_object, null_object),
                "name_comparator should treat two null pointers as equal");
    expect_true(!CGameObject::name_comparator(object, null_object),
                "name_comparator should not treat one null pointer as equal");

    auto type_id_a = std::make_shared<CGameObject>();
    type_id_a->setType("CEffect");
    type_id_a->setName("burn-one");
    type_id_a->setTypeId("burn");

    auto type_id_b = std::make_shared<CGameObject>();
    type_id_b->setType("CItem");
    type_id_b->setName("burn-two");
    type_id_b->setTypeId("burn");

    auto type_id_c = std::make_shared<CGameObject>();
    type_id_c->setType("CEffect");
    type_id_c->setName("burn-one");
    type_id_c->setTypeId("freeze");

    expect_true(CGameObject::name_comparator(type_id_a, type_id_b),
                "name_comparator should prefer matching typeId over type/name differences");
    expect_true(!CGameObject::name_comparator(type_id_a, type_id_c),
                "name_comparator should distinguish different typeIds");

    auto named_a = std::make_shared<CGameObject>();
    named_a->setType("CEffect");
    named_a->setName("haste");
    named_a->setLabel("first label");

    auto named_b = std::make_shared<CGameObject>();
    named_b->setType("CEffect");
    named_b->setName("haste");
    named_b->setLabel("second label");

    auto named_c = std::make_shared<CGameObject>();
    named_c->setType("CItem");
    named_c->setName("haste");

    expect_true(CGameObject::name_comparator(named_a, named_b),
                "name_comparator should fall back to type/name when both typeIds are empty");
    expect_true(!CGameObject::name_comparator(named_a, named_c),
                "name_comparator should distinguish type/name fallback mismatches");

    std::set<std::shared_ptr<CGameObject>> identity_set;
    identity_set.insert(type_id_a);
    identity_set.insert(type_id_b);
    expect_true(identity_set.size() == 2,
                "default shared_ptr sets should preserve distinct instances with matching configured ids");

    auto creature = std::make_shared<CCreature>();
    auto burn_effect_a = std::make_shared<CEffect>();
    burn_effect_a->setType("CEffect");
    burn_effect_a->setName("burn-one");
    burn_effect_a->setTypeId("burn");

    auto burn_effect_b = std::make_shared<CEffect>();
    burn_effect_b->setType("CEffect");
    burn_effect_b->setName("burn-two");
    burn_effect_b->setTypeId("burn");

    creature->addEffect(burn_effect_a);
    creature->addEffect(burn_effect_b);
    const auto effects = creature->getEffects();
    expect_true(effects.size() == 1 && effects.contains(burn_effect_a) && !effects.contains(burn_effect_b),
                "creature addEffect should de-duplicate current effects by configured comparator semantics");
}

void test_game_object_named_comparison_helpers_cover_explicit_semantics() {
    std::shared_ptr<CGameObject> null_object;
    auto first_item = std::make_shared<CItem>();
    first_item->setType("CItem");
    first_item->setName("potion-one");
    first_item->setTypeId("LifePotion");

    auto second_item = std::make_shared<CItem>();
    second_item->setType("CItem");
    second_item->setName("potion-two");
    second_item->setTypeId("LifePotion");

    expect_true(CGameObject::sameInstance(null_object, null_object),
                "sameInstance should treat two null pointers as the same instance");
    expect_true(CGameObject::sameInstance(first_item, first_item),
                "sameInstance should recognize the exact same item pointer");
    expect_true(!CGameObject::sameInstance(first_item, second_item),
                "sameInstance should distinguish two item instances with the same configured type");
    expect_true(CGameObject::sameConfiguredType(first_item, second_item),
                "sameConfiguredType should match two item instances with the same non-empty typeId");
    expect_true(CGameObject::name_comparator(first_item, second_item) ==
                    CGameObject::sameConfiguredType(first_item, second_item),
                "name_comparator should preserve the configured-type helper semantics");
    expect_true(!CGameObject::equivalentValue(first_item, second_item),
                "equivalentValue should not claim unsupported item object graphs are equivalent");

    auto named_a = std::make_shared<CGameObject>();
    named_a->setType("CEffect");
    named_a->setName("haste");

    auto named_b = std::make_shared<CGameObject>();
    named_b->setType("CEffect");
    named_b->setName("haste");

    auto named_c = std::make_shared<CGameObject>();
    named_c->setType("CEffect");
    named_c->setName("slow");

    auto named_with_type_id = std::make_shared<CGameObject>();
    named_with_type_id->setType("CEffect");
    named_with_type_id->setName("haste");
    named_with_type_id->setTypeId("configuredHaste");

    expect_true(CGameObject::sameConfiguredType(named_a, named_b),
                "sameConfiguredType should fall back to type/name when both typeIds are empty");
    expect_true(!CGameObject::sameConfiguredType(named_a, named_c),
                "sameConfiguredType should not collapse all objects with empty typeIds");
    expect_true(!CGameObject::sameConfiguredType(named_a, named_with_type_id),
                "sameConfiguredType should not fall back to type/name when only one typeId is empty");

    auto first_map = std::make_shared<CMap>();
    auto second_map = std::make_shared<CMap>();
    auto first_map_object = std::make_shared<CMapObject>();
    first_map_object->setName("sharedName");
    auto second_map_object = std::make_shared<CMapObject>();
    second_map_object->setName("sharedName");
    first_map->setObjects({first_map_object});
    second_map->setObjects({second_map_object});

    expect_true(!CGameObject::sameRuntimeIdentity(first_map_object, second_map_object),
                "sameRuntimeIdentity should distinguish the same object name on different owning maps");

    CTypes::register_type<CGameObject>();
    CTypes::register_type<CMapObject, CGameObject>();
    CTypes::register_type<CItem, CMapObject, CGameObject>();
    CTypes::register_type<CQuest, CGameObject>();
    auto game = std::make_shared<CGame>();
    game->getObjectHandler()->registerType("CGameObject", []() { return std::make_shared<CGameObject>(); });
    game->getObjectHandler()->registerType("CItem", []() { return std::make_shared<CItem>(); });
    game->getObjectHandler()->registerType("CQuest", []() { return std::make_shared<CQuest>(); });

    auto item_config = std::make_shared<json>();
    (*item_config)["class"] = "CItem";
    (*item_config)["properties"]["label"] = "Configured item";
    game->getObjectHandler()->registerConfig("ComparisonItem", item_config);

    auto configured_item = game->createObject<CItem>("ComparisonItem");
    auto same_config_item = game->createObject<CItem>("ComparisonItem");
    expect_true(configured_item && same_config_item, "test setup should create configured comparison items");
    expect_true(!CGameObject::sameInstance(configured_item, same_config_item),
                "two items from the same config should remain distinct live instances");
    expect_true(CGameObject::sameConfiguredType(configured_item, same_config_item),
                "two items from the same config should share configured type identity");

    auto cloned_item = configured_item->clone<CItem>();
    expect_true(static_cast<bool>(cloned_item), "test setup should clone configured items");
    expect_true(!CGameObject::sameInstance(configured_item, cloned_item),
                "cloned items should be distinct live instances");
    expect_true(CGameObject::sameConfiguredType(configured_item, cloned_item),
                "cloned items should retain their configured type identity");
    expect_true(!CGameObject::sameRuntimeIdentity(configured_item, cloned_item),
                "detached cloned items should not be treated as the same runtime map/name identity");

    auto quest_config = std::make_shared<json>();
    (*quest_config)["class"] = "CQuest";
    (*quest_config)["properties"]["description"] = "Compare configured quests";
    game->getObjectHandler()->registerConfig("ComparisonQuest", quest_config);

    auto first_quest = game->createObject<CQuest>("ComparisonQuest");
    auto second_quest = game->createObject<CQuest>("ComparisonQuest");
    expect_true(first_quest && second_quest, "test setup should create configured comparison quests");
    expect_true(!CGameObject::sameInstance(first_quest, second_quest),
                "two quests from the same config should remain distinct quest objects");
    expect_true(CGameObject::sameConfiguredType(first_quest, second_quest),
                "two quests from the same config should share configured quest identity");

    auto player = std::make_shared<CPlayer>();
    player->setGame(game);
    player->addQuest("ComparisonQuest");
    player->addQuest("ComparisonQuest");
    expect_true(player->getQuests().size() == 1,
                "player addQuest should de-duplicate quests by configured quest identity");

    auto source = std::make_shared<CGameObject>();
    source->setGame(game);
    source->setType("CGameObject");
    source->setTypeId("ConfiguredClone");
    source->setName("cloneSource");
    source->setLabel("Source Label");
    source->setDescription("source description");

    auto clone = source->clone<CGameObject>();
    expect_true(!CGameObject::sameInstance(source, clone), "clones should be distinct live instances");
    expect_true(CGameObject::sameConfiguredType(source, clone), "clones should retain the same configured typeId");
    expect_true(!CGameObject::sameRuntimeIdentity(source, clone),
                "detached clones should not be treated as the same runtime map/name identity");

    clone->setName(source->getName());
    expect_true(CGameObject::equivalentValue(source, clone),
                "equivalentValue should match clones after reviewed primitive values match");
    clone->setDescription("changed description");
    expect_true(!CGameObject::equivalentValue(source, clone),
                "equivalentValue should distinguish reviewed primitive value changes");

    auto cycle_a = std::make_shared<CGameObject>();
    cycle_a->setType("CGameObject");
    cycle_a->setName("cycle");
    cycle_a->setProperty("self", cycle_a);
    auto cycle_b = std::make_shared<CGameObject>();
    cycle_b->setType("CGameObject");
    cycle_b->setName("cycle");
    cycle_b->setProperty("self", cycle_b);

    expect_true(CGameObject::equivalentValue(cycle_a, cycle_a),
                "equivalentValue should handle a self-referential instance without recursion");
    expect_true(!CGameObject::equivalentValue(cycle_a, cycle_b),
                "equivalentValue should reject unsupported cyclic object-reference graphs safely");
}

class TypedSignalProbe : public CGameObject {
    V_META(TypedSignalProbe, CGameObject, V_METHOD(TypedSignalProbe, onPropertyChanged, void, std::string),
           V_METHOD(TypedSignalProbe, onInventoryChanged))

  public:
    void onPropertyChanged(std::string property_name) { changedProperties.insert(std::move(property_name)); }

    void onInventoryChanged() { ++inventoryChangedCalls; }

    std::set<std::string> changedProperties;
    int inventoryChangedCalls = 0;
};

void test_dynamic_property_cannot_spoof_typed_engine_signal() {
    CTypes::register_type_metadata<TypedSignalProbe, CGameObject>();

    auto object = std::make_shared<CGameObject>();
    auto probe = std::make_shared<TypedSignalProbe>();

    // A subscriber to the typed engine signal "inventoryChanged" (as CCreature emits
    // it). A dynamic/runtime property literally named "inventory" derives the same
    // "inventoryChanged" channel name in notifyPropertyChanged -> must be dropped fail
    // closed so the dynamic property cannot fire (spoof) the typed engine slot.
    object->connect("inventoryChanged", probe, "onInventoryChanged");
    object->connect("propertyChanged", probe, "onPropertyChanged");

    object->setStringProperty("inventory", "spoofed");
    drain_event_loop();

    expect_true(probe->inventoryChangedCalls == 0,
                "a dynamic property named like a typed engine signal must not fire the typed signal's slot");
    expect_true(probe->changedProperties.contains("inventory"),
                "the generic propertyChanged channel must still report the dynamic property change");

    // A non-colliding dynamic property still reaches its per-property "<name>Changed"
    // subscriber (the namespace guard only suppresses reserved typed-signal names).
    auto specific_probe = std::make_shared<TypedSignalProbe>();
    object->connect("threatChanged", specific_probe, "onInventoryChanged");
    object->setNumericProperty("threat", 1);
    drain_event_loop();
    expect_true(specific_probe->inventoryChangedCalls == 1,
                "a non-colliding dynamic property must still fire its per-property notification slot");
}

void test_typed_engine_signal_still_fires_directly() {
    CTypes::register_type_metadata<TypedSignalProbe, CGameObject>();
    auto creature = std::make_shared<CCreature>();
    auto probe = std::make_shared<TypedSignalProbe>();

    // The real typed engine signal (emitted directly via signal("inventoryChanged"))
    // must still reach its slot; the reserved-name guard only blocks the dynamic
    // property channel, never direct typed emission.
    creature->connect("inventoryChanged", probe, "onInventoryChanged");
    creature->addItem(std::make_shared<CItem>());
    drain_event_loop();

    expect_true(probe->inventoryChangedCalls >= 1,
                "directly emitted typed engine signals must still reach their slots");
}

void test_signal_slots_fail_closed_on_bad_config() {
    CTypes::register_type_metadata<PropertyChangeProbe, CGameObject>();

    auto object = std::make_shared<CGameObject>();
    auto valid_probe = std::make_shared<PropertyChangeProbe>();
    auto broken_probe = std::make_shared<PropertyChangeProbe>();

    // A config-driven slot that names a method which is not a valid reflective
    // target (missing / private / dispatch-meta) must not crash the event loop,
    // and must not starve a valid slot connected to the same signal.
    object->connect("propertyChanged", broken_probe, "missingSlotCallback");
    object->connect("propertyChanged", broken_probe, "_privateSlot");
    object->connect("propertyChanged", broken_probe, "invokeAction");
    object->connect("propertyChanged", broken_probe, "");
    object->connect("propertyChanged", valid_probe, "onPropertyChanged");

    object->notifyPropertyChanged("threat");
    drain_event_loop();

    expect_true(broken_probe->changedProperties.empty(),
                "invalid signal slot callbacks should no-op and fail closed instead of crashing");
    expect_true(valid_probe->changedProperties.contains("threat"),
                "a valid signal slot should still fire even when sibling slots fail closed");
}

// Characterization tests for bug-finder candidates that source review judged NOT to be bugs.
// They lock in the current (correct) behavior; if any candidate were actually a defect, the
// corresponding assertion would fail instead of pass.

void test_effect_applies_for_exactly_its_duration_without_underflow() {
    auto effect = std::make_shared<CEffect>();
    effect->setDuration(3);
    expect_true(effect->getTimeLeft() == 3, "effect timeLeft should initialize to its duration");
    expect_true(effect->getTimeTotal() == 3, "effect timeTotal should initialize to its duration");

    // apply() ignores its creature argument; it runs onEffect() and decrements timeLeft.
    for (int tick = 1; tick <= 3; ++tick) {
        effect->apply(nullptr);
    }
    expect_true(effect->getTimeLeft() == 0, "effect should be spent after exactly duration applications");
    expect_true(effect->getTimeTotal() == 3, "effect timeTotal should be preserved across applications");

    // Applying a spent effect must be a no-op and must never drive timeLeft below zero.
    effect->apply(nullptr);
    effect->apply(nullptr);
    expect_true(effect->getTimeLeft() == 0, "applying a spent effect must not drive timeLeft negative");
}

void test_creature_get_dmg_hit_chance_is_not_inverted() {
    srand(20260630u); // deterministic dice sequence for this characterization

    auto make_combatant = [](int hit, int attack) {
        auto stats = std::make_shared<CStats>();
        stats->setMainStat("intelligence");
        stats->setHit(hit);
        stats->setAttack(attack);
        stats->setCrit(0);   // disable critical doubling
        stats->setDmgMin(5); // fixed damage so a connecting swing always yields exactly 5
        stats->setDmgMax(5);
        stats->setDamage(0);
        auto creature = std::make_shared<CCreature>();
        creature->setBaseStats(stats);
        creature->setLevelStats(std::make_shared<CStats>());
        creature->setLevel(0); // getStats() == baseStats: no level/equipment/effect bonuses
        return creature;
    };

    const int iterations = 300;

    // Boundary: hit=100 with no attack penalty connects on every swing.
    auto alwaysHit = make_combatant(100, 0);
    int alwaysHitConnects = 0;
    for (int i = 0; i < iterations; ++i) {
        if (alwaysHit->getDmg() > 0) {
            ++alwaysHitConnects;
        }
    }
    expect_true(alwaysHitConnects == iterations, "hit=100 should connect on every swing (returns damage, never 0)");

    // Boundary: hit=0 with no attack bonus misses every swing.
    auto alwaysMiss = make_combatant(0, 0);
    int alwaysMissConnects = 0;
    for (int i = 0; i < iterations; ++i) {
        if (alwaysMiss->getDmg() > 0) {
            ++alwaysMissConnects;
        }
    }
    expect_true(alwaysMissConnects == 0, "hit=0 should miss every swing (returns 0)");

    // Direction: at a fixed hit chance, MORE attack must increase (not invert) hit frequency.
    auto lowAttack = make_combatant(50, 0);
    auto highAttack = make_combatant(50, 100);
    int lowConnects = 0;
    int highConnects = 0;
    for (int i = 0; i < iterations; ++i) {
        if (lowAttack->getDmg() > 0) {
            ++lowConnects;
        }
        if (highAttack->getDmg() > 0) {
            ++highConnects;
        }
    }
    expect_true(highConnects > lowConnects, "higher attack must increase, not invert, hit frequency");
    expect_true(highConnects == iterations, "attack=100 fully offsets a 0-99 dice roll, so every swing connects");
}

// CInteraction routes its effect to the caster or the opponent via effectRoutesToCaster
// (EPIC_06/STORY_01/SUBSTORY_02): an explicit selfTarget always routes to the caster, a
// legacy Buff-tagged effect without selfTarget stays a self-buff, and every other effect
// routes to the opponent -- so routing no longer depends solely on effect tags while old
// buff configs still work.
void test_interaction_effect_routes_to_caster_via_self_target() {
    auto interaction = std::make_shared<CInteraction>();

    auto buff = std::make_shared<CEffect>();
    buff->addTag(CTag::Buff);
    auto debuff = std::make_shared<CEffect>(); // untagged -> opponent

    // No selfTarget: legacy tag-based routing is preserved exactly.
    expect_true(interaction->effectRoutesToCaster(buff),
                "a Buff effect without selfTarget keeps its legacy self-buff routing");
    expect_true(!interaction->effectRoutesToCaster(debuff),
                "a non-buff effect without selfTarget routes to the opponent");
    expect_true(!interaction->effectRoutesToCaster(nullptr),
                "a null effect without selfTarget does not route to the caster");

    // selfTarget overrides tags: the effect always routes to the caster.
    interaction->setSelfTarget(true);
    expect_true(interaction->effectRoutesToCaster(debuff),
                "selfTarget routes an otherwise-opponent effect to the caster");
    expect_true(interaction->effectRoutesToCaster(buff), "selfTarget keeps a buff on the caster");
}

} // namespace

int main() {
    pybind11::scoped_interpreter guard{};
    test_signal_slots_fail_closed_on_bad_config();
    test_dynamic_property_cannot_spoof_typed_engine_signal();
    test_typed_engine_signal_still_fires_directly();
    test_effect_applies_for_exactly_its_duration_without_underflow();
    test_creature_get_dmg_hit_chance_is_not_inverted();
    test_interaction_effect_routes_to_caster_via_self_target();
    test_tooltip_handler_builds_labels_descriptions_and_item_bonuses();
    test_market_guard_paths_and_item_transfers();
    test_market_prices_are_bounded_and_non_exploitable();
    test_player_quest_setters_filter_nulls_and_skip_duplicates();
    test_creature_direct_setters_notify_property_observers();
    test_player_quest_setters_notify_property_observers();
    test_map_direct_state_setters_notify_property_observers();
    test_game_object_get_map_prefers_owner_and_falls_back_to_active_map();
    test_game_object_equivalent_value_covers_supported_property_types();
    test_game_object_property_helpers_and_owned_tile_movement();
    test_animation_property_events_invalidate_cached_graphics_object();
    test_creature_inventory_equipment_and_ratio_helpers();
    test_no_archetype_creature_stats_keep_legacy_composition();
    test_creature_stat_precedence_orders_sources_and_main_stat();
    test_creature_class_main_stat_is_authoritative_over_race();
    test_creature_archetype_identity_accessors_use_fallbacks();
    test_creature_effective_interactions_compose_and_dedupe_sources();
    test_creature_effective_interactions_compose_archetype_sources();
    test_creature_action_merge_dedupes_by_type_id();
    test_creature_duplicate_attack_from_race_and_class_collapses_to_single_identity();
    test_no_archetype_creature_level_up_mutates_actions_via_levelling();
    test_game_object_comparator_and_identity_sets_document_current_semantics();
    test_game_object_named_comparison_helpers_cover_explicit_semantics();

    return finish_tests();
}
