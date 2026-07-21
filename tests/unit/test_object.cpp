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
#include "core/CJsonUtil.h"
#include "core/CStats.h"
#include "core/CMap.h"
#include "core/CTypeRegistration.h"
#include "core/CTypes.h"
#include "gui/CAnimation.h"
#include "handler/CTooltipHandler.h"
#include "object/CCreature.h"
#include "object/CCreatureClass.h"
#include "object/CCreatureClassTrack.h"
#include "object/CCreatureRace.h"
#include "object/CCreatureTemplate.h"
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

void test_equip_item_same_instance_is_noop_and_keeps_cursed_lock() {
    type_registration::registerCoreTypes();
    CTypes::register_type<CMapObject, CGameObject>();
    CTypes::register_type<CItem, CMapObject, CGameObject>();
    CTypes::register_type<CCreature, CMapObject, CGameObject>();

    auto game = std::make_shared<CGame>();
    auto map = std::make_shared<CMap>();
    map->setGame(game);
    game->setMap(map);
    game->getObjectHandler()->registerConfig(
        "slotConfiguration", CJsonUtil::from_string(R"({"class":"CSlotConfig","properties":{"configuration":{)"
                                                    R"("0":{"class":"CSlot","properties":{"types":["CItem"]}},)"
                                                    R"("3":{"class":"CSlot","properties":{"types":["CItem"]}}}}})",
                                                    "slotConfiguration"));

    auto creature = std::make_shared<CCreature>();
    creature->setGame(game);
    creature->setName("equipLockTester");
    creature->setBaseStats(stats_with_main(10, 10));

    auto cursed_armor = std::make_shared<CItem>();
    cursed_armor->setTypeId("cursedTestArmor");
    cursed_armor->addTag(CTag::Cursed);
    creature->setEquipped({{"3", cursed_armor}});

    creature->equipItem("3", cursed_armor);
    expect_true(CGameObject::sameInstance(creature->getItemAtSlot("3"), cursed_armor),
                "re-equipping the equipped cursed instance must be a no-op, not an unequip");
    expect_true(!creature->hasInInventory(cursed_armor),
                "re-equipping the equipped cursed instance must not move it into the inventory");

    creature->equipItem("3", nullptr);
    expect_true(CGameObject::sameInstance(creature->getItemAtSlot("3"), cursed_armor),
                "cursed items must stay locked against explicit unequip");

    auto plain_sword = std::make_shared<CItem>();
    plain_sword->setTypeId("plainTestSword");
    creature->setEquipped({{"0", plain_sword}, {"3", cursed_armor}});

    creature->equipItem("0", plain_sword);
    expect_true(CGameObject::sameInstance(creature->getItemAtSlot("0"), plain_sword),
                "re-equipping the equipped instance must be a no-op for ordinary items too");
    expect_true(!creature->hasInInventory(plain_sword),
                "a same-instance re-equip must not duplicate the item into the inventory");

    creature->equipItem("0", nullptr);
    expect_true(creature->getItemAtSlot("0") == nullptr, "ordinary items must still unequip normally");
    expect_true(creature->hasInInventory(plain_sword), "a normal unequip must return the item to the inventory");

    cursed_armor->removeTag(CTag::Cursed);
    creature->equipItem("3", nullptr);
    expect_true(creature->getItemAtSlot("3") == nullptr, "lifting the curse must unlock the slot again");
    expect_true(creature->hasInInventory(cursed_armor), "an unlocked unequip must return the item to the inventory");
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

void test_racial_progression_defaults_keep_composition_neutral() {
    // [EPIC_08][STORY_04][SUBSTORY_01] Model racial advancement separately from class
    // level -- NEUTRALITY. Racial advancement (CCreatureRace::racialLevelStats applied
    // once per CCreature::racialLevel) is future-gated scaffolding: with the neutral
    // defaults (racialLevel == 0 and/or an empty race progression) it contributes
    // exactly zero, so every existing creature -- legacy or composed -- keeps a
    // bit-identical stat block and the class level semantics are untouched. There is
    // deliberately NO XP wiring for racialLevel, so nothing can raise it implicitly.
    //
    // The per-property comparison below reflects over CStats via getProperty<int>,
    // which needs the CStats any-cast converter registered (see the registration
    // note in test_racial_level_round_trips_through_meta_property_binding).
    // Register it here explicitly so this test does not depend on test order.
    CTypes::register_type<CGameObject>();
    CTypes::register_type<CStats, CGameObject>();

    auto same_int_properties = [](const std::shared_ptr<CStats> &before, const std::shared_ptr<CStats> &after) {
        bool same = before->getMainStat() == after->getMainStat();
        before->meta()->for_all_properties(before, [&](auto property) {
            if (property->value_type() != std::type_index(typeid(int))) {
                return;
            }
            same = same && before->getProperty<int>(property->name()) == after->getProperty<int>(property->name());
        });
        return same;
    };

    // Shared legacy shape reused from the existing composition tests: base 10 int,
    // +2 int per class level, level 3.
    auto make_creature = []() {
        auto creature = std::make_shared<CCreature>();
        auto base = std::make_shared<CStats>();
        base->setMainStat("intelligence");
        base->setIntelligence(10);
        base->setStamina(6);
        creature->setBaseStats(base);
        auto level_stats = std::make_shared<CStats>();
        level_stats->setIntelligence(2);
        creature->setLevelStats(level_stats);
        creature->setLevel(3);
        return creature;
    };

    // (a) Legacy creature (no race, no creatureClass): racialLevel alone must not
    // contribute -- racial progression is race-carried, and the legacy path stays exact.
    auto legacy = make_creature();
    auto legacy_before = legacy->getStats();
    expect_true(legacy->getRacialLevel() == 0, "racialLevel should default to 0 (zero contribution)");
    expect_true(legacy_before->getIntelligence() == 10 + 3 * 2,
                "the legacy creature should keep the exact legacy composition (base + level*levelStats)");
    legacy->setRacialLevel(5);
    expect_true(same_int_properties(legacy_before, legacy->getStats()),
                "a racialLevel on a legacy creature (no race) must not change the composed stats");
    expect_true(legacy->getLevel() == 3, "racialLevel must not disturb the class-driven level");

    // (b) Composed creature whose race has NO authored racial progression: a nonzero
    // racialLevel composes bit-identically (default-empty progression => zero growth).
    auto composed = make_creature();
    auto race = std::make_shared<CCreatureRace>();
    composed->setRace(race);
    auto composed_before = composed->getStats();
    composed->setRacialLevel(4);
    expect_true(same_int_properties(composed_before, composed->getStats()),
                "racial levels over an empty race progression must contribute exactly zero");

    // (c) Composed creature whose race HAS racial progression but racialLevel stays at
    // the default 0: attaching the progression must not change anything.
    auto gated = make_creature();
    auto progressive_race = std::make_shared<CCreatureRace>();
    gated->setRace(progressive_race);
    auto gated_before = gated->getStats();
    auto racial_growth = std::make_shared<CStats>();
    racial_growth->setStamina(3);
    racial_growth->setStrength(2);
    progressive_race->setRacialLevelStats(racial_growth);
    expect_true(same_int_properties(gated_before, gated->getStats()),
                "race progression with the default racialLevel of 0 must contribute exactly zero");
}

void test_racial_level_composes_race_progression_independently_of_class_level() {
    // [EPIC_08][STORY_04][SUBSTORY_01] Model racial advancement separately from class
    // level -- CAPABILITY. A race configured with racialLevelStats plus a creature
    // racialLevel of N composes exactly N * racialLevelStats, folded at the documented
    // position (after all base sources, opening the per-level growth block ahead of
    // creatureClass.levelStats and creature.levelStats). The racial contribution is
    // independent of -- and coexists with -- the class level growth: changing the class
    // level does not alter the racial contribution and vice versa.
    //
    // The expected-vs-actual sweep below reflects over CStats via getProperty<int>,
    // so register the CStats any-cast converter explicitly (idempotent; see the
    // registration note in test_racial_level_round_trips_through_meta_property_binding).
    CTypes::register_type<CGameObject>();
    CTypes::register_type<CStats, CGameObject>();

    auto creature = std::make_shared<CCreature>();

    auto base = std::make_shared<CStats>();
    base->setMainStat("intelligence");
    base->setIntelligence(10);
    base->setStamina(6);
    base->setStrength(4);
    creature->setBaseStats(base);

    auto creature_growth = std::make_shared<CStats>();
    creature_growth->setIntelligence(1);
    creature->setLevelStats(creature_growth);

    auto race_base = std::make_shared<CStats>();
    race_base->setStamina(2);
    auto racial_growth = std::make_shared<CStats>();
    racial_growth->setStamina(3);
    racial_growth->setStrength(2);
    auto race = std::make_shared<CCreatureRace>();
    race->setBaseStats(race_base);
    race->setRacialLevelStats(racial_growth);
    creature->setRace(race);

    auto class_growth = std::make_shared<CStats>();
    class_growth->setIntelligence(2);
    class_growth->setStamina(1);
    auto klass = std::make_shared<CCreatureClass>();
    klass->setLevelStats(class_growth);
    creature->setCreatureClass(klass);

    const int class_level = 3;
    const int racial_level = 2;
    creature->setLevel(class_level);
    creature->setRacialLevel(racial_level);

    // Independently recompute the documented composition:
    //   race.baseStats -> creature.baseStats -> racialLevel * race.racialLevelStats ->
    //   class_level * (class levelStats + creature levelStats).
    auto expected = std::make_shared<CStats>();
    expected->setMainStat(base->getMainStat());
    expected->addBonus(race_base);
    expected->addBonus(base);
    for (int i = 0; i < racial_level; ++i) {
        expected->addBonus(racial_growth);
    }
    for (int i = 0; i < class_level; ++i) {
        expected->addBonus(class_growth);
    }
    for (int i = 0; i < class_level; ++i) {
        expected->addBonus(creature_growth);
    }

    auto actual = creature->getStats();
    actual->meta()->for_all_properties(actual, [&](auto property) {
        if (property->value_type() != std::type_index(typeid(int))) {
            return;
        }
        int actual_value = actual->getProperty<int>(property->name());
        int expected_value = expected->getProperty<int>(property->name());
        if (actual_value != expected_value) {
            std::cerr << "RACIAL STAT DIFF [" << property->name() << "] expected " << expected_value << " but got "
                      << actual_value << "\n";
        }
        expect_true(actual_value == expected_value,
                    "composed stats should fold racialLevel * race.racialLevelStats alongside (not instead of) "
                    "the class level growth");
    });
    expect_true(actual->getMainStat() == "intelligence",
                "racial progression is numeric-only and must not disturb the selected main stat");

    // Independence, direction 1: raising the CLASS level adds exactly the class +
    // creature growth -- the racial contribution stays constant.
    creature->setLevel(class_level + 2);
    auto after_class_levels = creature->getStats();
    expect_true(after_class_levels->getIntelligence() == actual->getIntelligence() + 2 * (2 + 1),
                "raising the class level should add exactly the class+creature growth per level");
    expect_true(after_class_levels->getStamina() == actual->getStamina() + 2 * 1,
                "raising the class level should not change the racial stamina contribution");
    expect_true(after_class_levels->getStrength() == actual->getStrength(),
                "raising the class level should leave the racial-only strength contribution untouched");

    // Independence, direction 2: raising the RACIAL level adds exactly the racial
    // growth -- the class-level contribution stays constant.
    creature->setRacialLevel(racial_level + 3);
    auto after_racial_levels = creature->getStats();
    expect_true(after_racial_levels->getStamina() == after_class_levels->getStamina() + 3 * 3,
                "raising the racial level should add exactly the racial stamina growth per racial level");
    expect_true(after_racial_levels->getStrength() == after_class_levels->getStrength() + 3 * 2,
                "raising the racial level should add exactly the racial strength growth per racial level");
    expect_true(after_racial_levels->getIntelligence() == after_class_levels->getIntelligence(),
                "raising the racial level should not alter the class-level intelligence contribution");
    expect_true(creature->getLevel() == class_level + 2 && creature->getRacialLevel() == racial_level + 3,
                "class level and racial level are distinct, independently stored fields");
}

void test_racial_level_round_trips_through_meta_property_binding() {
    // [EPIC_08][STORY_04][SUBSTORY_01] Serialization: racialLevel (creature) and
    // racialLevelStats (race) are declared V_META properties, so they round-trip
    // through the same meta property binding save/clone serialization uses for
    // every other creature property. Pin the binding both ways (setter -> property
    // read, property write -> getter).
    //
    // Reflective V_META access routes through vstd::any_cast converters that only
    // exist for types registered via CTypes::register_type: property_impl::
    // object_from_any (vstd/vmeta.h) casts the shared_ptr<CGameObject> handle from
    // CGameObject::ptr() to the property's DECLARING type, and without the
    // registered converter that cast falls through to std::any_cast and dies with
    // bad_any_cast. This per-domain test binary does not run the full module type
    // registration, so register the exact chain this test reflects over (CCreature,
    // CCreatureRace, and the shared_ptr<CStats> property payload), the same way the
    // equip and tooltip tests in this file register theirs. Registration is global
    // and idempotent, so repeating it here is safe regardless of test order.
    CTypes::register_type<CGameObject>();
    CTypes::register_type<CMapObject, CGameObject>();
    CTypes::register_type<CCreature, CMapObject, CGameObject>();
    CTypes::register_type<CCreatureRace, CGameObject>();
    CTypes::register_type<CStats, CGameObject>();

    auto creature = std::make_shared<CCreature>();
    expect_true(creature->getProperty<int>("racialLevel") == 0,
                "the racialLevel meta property should expose the neutral default of 0");
    creature->setProperty("racialLevel", 4);
    expect_true(creature->getRacialLevel() == 4,
                "writing the racialLevel meta property should reach the racial level field");
    creature->setRacialLevel(7);
    expect_true(creature->getProperty<int>("racialLevel") == 7,
                "the racialLevel setter should be visible through the meta property binding");

    auto race = std::make_shared<CCreatureRace>();
    auto growth = std::make_shared<CStats>();
    growth->setStamina(3);
    race->setProperty("racialLevelStats", growth);
    expect_true(race->getRacialLevelStats()->getStamina() == 3,
                "writing the racialLevelStats meta property should reach the race progression field");
    expect_true(race->getProperty<std::shared_ptr<CStats>>("racialLevelStats")->getStamina() == 3,
                "the racialLevelStats meta property should read back the authored progression");
    race->setRacialLevelStats(nullptr);
    expect_true(race->getRacialLevelStats() != nullptr && race->getRacialLevelStats()->getStamina() == 0,
                "a null racial progression should normalize to an empty (zero-contribution) CStats");
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

void test_player_composed_stats_reflect_race_and_class_archetype() {
    // [EPIC_06][STORY_02][SUBSTORY_04] Implement composed player stats.
    // A CPlayer's effective stats are COMPOSED from its own base stats PLUS the
    // contributions of its archetype (race + creatureClass), not a single flat stat
    // block. CPlayer inherits the shared composition primitive CCreature::getStats
    // (docs/design/creature_archetypes.md, "Creature stat precedence contract"), so a
    // player that carries a race and/or a creatureClass folds them in at the documented
    // positions:
    //   race.baseStats -> creatureClass.baseStats -> player.baseStats ->
    //   creatureClass.levelStats (per level) -> player.levelStats (per level).
    // The composed mainStat is class-authoritative (falls back to the player's base
    // mainStat only when the class declares none). This pins that contract for the
    // player type exactly as the creature-stat tests pin it for creatures.
    auto player = std::make_shared<CPlayer>();

    // Player's own base: declares a mainStat that CONFLICTS with the class main stat so
    // the class-authoritative selection is observable, and contributes intelligence.
    auto playerBase = std::make_shared<CStats>();
    playerBase->setMainStat("strength");
    playerBase->setStrength(4);
    playerBase->setIntelligence(6);
    playerBase->setStamina(5);
    player->setBaseStats(playerBase);

    // Race archetype contribution (flat baseline every member of the race has).
    auto raceBase = std::make_shared<CStats>();
    raceBase->setStrength(2);
    raceBase->setStamina(3);
    auto race = std::make_shared<CCreatureRace>();
    race->setBaseStats(raceBase);
    player->setRace(race);
    player->setRaceId("humanRace");

    // Class archetype contribution (base + per-level growth) and the authoritative main
    // stat for the composed block.
    auto classBase = std::make_shared<CStats>();
    classBase->setIntelligence(7);
    classBase->setStrength(1);
    auto classLevel = std::make_shared<CStats>();
    classLevel->setIntelligence(2);
    classLevel->setStamina(1);
    auto klass = std::make_shared<CCreatureClass>();
    klass->setMainStat("intelligence");
    klass->setBaseStats(classBase);
    klass->setLevelStats(classLevel);
    player->setCreatureClass(klass);
    player->setPlayerClassId("mageClass");

    // Player's own per-level growth, layered after the class growth.
    auto playerLevel = std::make_shared<CStats>();
    playerLevel->setStrength(1);
    player->setLevelStats(playerLevel);

    const int level = 2;
    player->setLevel(level);

    expect_true(player->usesArchetypeComposition(),
                "a player carrying a race and/or creatureClass should use the composed stat path");

    // Independently recompute the expected composition in the documented order (no
    // equipment/effects here so the archetype contribution is isolated).
    auto expected = std::make_shared<CStats>();
    expected->setMainStat(klass->getMainStat()); // class is authoritative for mainStat
    expected->addBonus(raceBase);
    expected->addBonus(classBase);
    expected->addBonus(playerBase);
    for (int i = 0; i < level; ++i) {
        expected->addBonus(classLevel);
    }
    for (int i = 0; i < level; ++i) {
        expected->addBonus(playerLevel);
    }

    auto actual = player->getStats();

    expect_true(actual->getMainStat() == "intelligence",
                "composed player mainStat should be the class-authoritative main stat over the base main stat");

    actual->meta()->for_all_properties(actual, [&](auto property) {
        if (property->value_type() != std::type_index(typeid(int))) {
            return;
        }
        int actual_value = actual->getProperty<int>(property->name());
        int expected_value = expected->getProperty<int>(property->name());
        if (actual_value != expected_value) {
            std::cerr << "PLAYER STAT DIFF [" << property->name() << "] expected " << expected_value << " but got "
                      << actual_value << "\n";
        }
        expect_true(actual_value == expected_value,
                    "composed player getStats should equal race + class base + player base + "
                    "level*(class + player) level growth");
    });

    // Sanity: the class contribution is really part of the composition -- clearing the
    // creatureClass drops exactly the class base + class per-level growth from the total.
    player->setCreatureClass(nullptr);
    const int classIntContribution = 7 /*classBase*/ + level * 2 /*classLevel*/;
    expect_true(player->getStats()->getIntelligence() == actual->getIntelligence() - classIntContribution,
                "removing the creatureClass should remove exactly the class intelligence contribution");
}

void test_player_without_archetype_falls_back_to_base_stats() {
    // [EPIC_06][STORY_02][SUBSTORY_04] Legacy fallback for players.
    // A player with NO race and NO creatureClass archetype object must fall back to its
    // own base stats unchanged (docs/design/creature_archetypes.md, "Legacy fallback
    // compatibility contract"). The string identity fields (raceId / playerClassId) are
    // metadata only: on their own -- with no backing archetype object -- they must NOT
    // inject any stat contribution, so the composed block is bit-for-bit the base block.
    auto player = std::make_shared<CPlayer>();

    auto base = std::make_shared<CStats>();
    base->setMainStat("agility");
    base->setStrength(8);
    base->setAgility(9);
    base->setStamina(7);
    base->setIntelligence(3);
    base->setArmor(2);
    player->setBaseStats(base);

    // Identity strings without backing archetype objects: these describe the player's
    // archetype but must not contribute stats by themselves.
    player->setRaceId("humanRace");
    player->setPlayerClassId("WarriorClass");

    expect_true(!player->usesArchetypeComposition(),
                "a player with only identity strings (no race/class object) must stay on the legacy stat path");

    auto stats = player->getStats();

    expect_true(stats->getMainStat() == base->getMainStat(),
                "no-archetype player getStats should keep the base mainStat unchanged");

    stats->meta()->for_all_properties(stats, [&](auto property) {
        if (property->value_type() != std::type_index(typeid(int))) {
            return;
        }
        int actual_value = stats->getProperty<int>(property->name());
        int expected_value = base->getProperty<int>(property->name());
        expect_true(actual_value == expected_value,
                    "no-archetype player getStats should equal the base stats unchanged (no archetype bonus)");
    });
}

void test_no_template_creature_composes_bit_identically_to_baseline() {
    // [EPIC_08][STORY_02][SUBSTORY_01] Introduce CCreatureTemplate definition object.
    // Neutrality invariant: the template layer is OPTIONAL, and a creature with NO
    // templates (every creature on current content) composes bit-identically to the
    // pre-template contracts -- both on the legacy path (no race/class) and on the
    // composed race/class path. Explicitly assigning an empty template set must be
    // exactly as neutral as never touching the property.

    // Legacy creature: same source values as the pinned legacy composition tests.
    auto legacy = std::make_shared<CCreature>();
    auto legacyBase = std::make_shared<CStats>();
    legacyBase->setMainStat("intelligence");
    legacyBase->setIntelligence(10);
    legacyBase->setStrength(4);
    legacyBase->setStamina(6);
    legacy->setBaseStats(legacyBase);
    auto legacyLevelStats = std::make_shared<CStats>();
    legacyLevelStats->setIntelligence(2);
    legacyLevelStats->setStrength(1);
    legacy->setLevelStats(legacyLevelStats);
    const int legacyLevel = 3;
    legacy->setLevel(legacyLevel);

    legacy->setTemplates({}); // explicit empty set == never configured
    expect_true(legacy->getTemplates().empty(), "an explicitly empty template set stays empty");
    expect_true(!legacy->usesArchetypeComposition(),
                "a creature with no race/class and no templates must stay on the legacy stat path");
    expect_true(legacy->getScale() == legacyLevel, "getScale of a no-template creature stays level + sw exactly");

    auto legacyExpected = std::make_shared<CStats>();
    legacyExpected->setMainStat(legacyBase->getMainStat());
    legacyExpected->addBonus(legacyBase);
    for (int i = 0; i < legacyLevel; ++i) {
        legacyExpected->addBonus(legacyLevelStats);
    }
    auto legacyActual = legacy->getStats();
    expect_true(legacyActual->getMainStat() == legacyExpected->getMainStat(),
                "no-template legacy creature getStats should keep the baseStats mainStat");
    legacyActual->meta()->for_all_properties(legacyActual, [&](auto property) {
        if (property->value_type() != std::type_index(typeid(int))) {
            return;
        }
        expect_true(legacyActual->getProperty<int>(property->name()) ==
                        legacyExpected->getProperty<int>(property->name()),
                    "no-template legacy creature getStats should match the legacy composition bit-identically");
    });

    // Composed creature (race + class): the template stage contributes nothing.
    auto composed = std::make_shared<CCreature>();
    auto composedBase = std::make_shared<CStats>();
    composedBase->setMainStat("strength");
    composedBase->setStrength(4);
    composedBase->setIntelligence(6);
    composed->setBaseStats(composedBase);
    auto raceBase = std::make_shared<CStats>();
    raceBase->setStrength(2);
    raceBase->setStamina(3);
    auto race = std::make_shared<CCreatureRace>();
    race->setBaseStats(raceBase);
    composed->setRace(race);
    auto classBase = std::make_shared<CStats>();
    classBase->setIntelligence(7);
    auto classLevel = std::make_shared<CStats>();
    classLevel->setIntelligence(2);
    auto klass = std::make_shared<CCreatureClass>();
    klass->setMainStat("intelligence");
    klass->setBaseStats(classBase);
    klass->setLevelStats(classLevel);
    composed->setCreatureClass(klass);
    const int composedLevel = 2;
    composed->setLevel(composedLevel);

    composed->setTemplates({}); // explicit empty set == never configured

    auto composedExpected = std::make_shared<CStats>();
    composedExpected->setMainStat(klass->getMainStat());
    composedExpected->addBonus(raceBase);
    composedExpected->addBonus(classBase);
    composedExpected->addBonus(composedBase);
    for (int i = 0; i < composedLevel; ++i) {
        composedExpected->addBonus(classLevel);
    }
    auto composedActual = composed->getStats();
    expect_true(composedActual->getMainStat() == "intelligence",
                "no-template composed creature keeps the class-authoritative mainStat");
    composedActual->meta()->for_all_properties(composedActual, [&](auto property) {
        if (property->value_type() != std::type_index(typeid(int))) {
            return;
        }
        expect_true(composedActual->getProperty<int>(property->name()) ==
                        composedExpected->getProperty<int>(property->name()),
                    "no-template composed creature getStats should match the race/class composition bit-identically");
    });
    expect_true(composed->getScale() == composedLevel,
                "getScale of a no-template composed creature stays level + sw exactly");
    expect_true(composed->getEffectiveInteractions().empty(),
                "an empty template set adds no actions to the effective interaction set");
}

void test_creature_templates_compose_after_race_and_class_in_order() {
    // [EPIC_08][STORY_02][SUBSTORY_01] Capability: templates are an ORDERED,
    // optional overlay applied AFTER race/class composition. Stat adjustments fold
    // in after the race/class/creature stack; template actions merge after class
    // sources (so they override class duplicates) but before the creature's own
    // concrete actions (which stay most specific); multiple templates apply in
    // ascending `order`; scale adjustments accumulate.
    auto interaction = [](const std::string &typeId, const std::string &name) {
        auto action = std::make_shared<CInteraction>();
        action->setType("CInteraction");
        action->setTypeId(typeId);
        action->setName(name);
        return action;
    };

    auto creature = std::make_shared<CCreature>();
    auto base = std::make_shared<CStats>();
    base->setMainStat("intelligence");
    base->setIntelligence(10);
    creature->setBaseStats(base);
    auto levelStats = std::make_shared<CStats>();
    levelStats->setIntelligence(2);
    creature->setLevelStats(levelStats);
    const int level = 2;
    creature->setLevel(level);

    auto raceBase = std::make_shared<CStats>();
    raceBase->setIntelligence(3);
    auto race = std::make_shared<CCreatureRace>();
    race->setBaseStats(raceBase);
    creature->setRace(race);

    auto classBase = std::make_shared<CStats>();
    classBase->setIntelligence(4);
    auto classAttack = interaction("Attack", "classAttack");
    auto klass = std::make_shared<CCreatureClass>();
    klass->setBaseStats(classBase);
    klass->setActions({classAttack});
    creature->setCreatureClass(klass);

    // Two template overlays with distinct ordering keys; inserted out of order to
    // prove getOrderedTemplates sorts by the `order` key, not insertion order.
    auto first = std::make_shared<CCreatureTemplate>();
    first->setTypeId("eliteTemplate");
    first->setOrder(10);
    first->setScaleAdjustment(1);
    auto firstStats = std::make_shared<CStats>();
    firstStats->setIntelligence(5);
    first->setStatAdjustments(firstStats);
    auto firstEmpower = interaction("Empower", "firstEmpower");
    auto templateAttack = interaction("Attack", "templateAttack");
    first->setActions({firstEmpower, templateAttack});

    auto second = std::make_shared<CCreatureTemplate>();
    second->setTypeId("diseasedTemplate");
    second->setOrder(20);
    second->setScaleAdjustment(2);
    auto secondStats = std::make_shared<CStats>();
    secondStats->setIntelligence(7);
    second->setStatAdjustments(secondStats);
    auto secondEmpower = interaction("Empower", "secondEmpower");
    second->setActions({secondEmpower});

    creature->setTemplates({second, first});

    auto orderedTemplates = creature->getOrderedTemplates();
    expect_true(orderedTemplates.size() == 2 && orderedTemplates[0] == first && orderedTemplates[1] == second,
                "getOrderedTemplates should sort templates by ascending order key, not insertion order");

    // Stats: race + class + creature base + level growth + both templates.
    const int expected_intelligence = 3 /*race*/ + 4 /*class*/ + 10 /*base*/ + level * 2 /*levelStats*/ +
                                      5 /*first template*/ + 7 /*second template*/;
    auto stats = creature->getStats();
    expect_true(stats->getIntelligence() == expected_intelligence,
                "template stat adjustments should layer on top of the race/class/creature composition");
    expect_true(stats->getMainStat() == "intelligence", "templates must not disturb the composed mainStat selection");

    // Scale: level + sw + the accumulated template scale adjustments.
    expect_true(creature->getScale() == level + 1 + 2,
                "template scale adjustments should accumulate on top of level + sw");

    auto effectiveContains = [&creature](const std::shared_ptr<CInteraction> &action) {
        auto effective = creature->getEffectiveInteractions();
        return effective.find(action) != effective.end();
    };

    // Template actions apply AFTER class sources: the first template's Attack
    // overrides the class Attack; the later-ordered template wins the Empower
    // duplicate between the two templates.
    expect_true(effectiveContains(templateAttack) && !effectiveContains(classAttack),
                "a template action should override a duplicate class action (templates apply after race/class)");
    expect_true(effectiveContains(secondEmpower) && !effectiveContains(firstEmpower),
                "the later-ordered template should win duplicate action keys between templates");

    // The ordering key drives the fold-in: raising the first template's order past
    // the second flips the Empower winner.
    first->setOrder(30);
    expect_true(effectiveContains(firstEmpower) && !effectiveContains(secondEmpower),
                "changing the order key must change the template application order");
    first->setOrder(10);

    // The creature's own concrete actions stay most specific over template additions.
    auto concreteAttack = interaction("Attack", "concreteAttack");
    creature->addAction(concreteAttack);
    expect_true(effectiveContains(concreteAttack) && !effectiveContains(templateAttack),
                "concrete creature actions should stay most specific over template action additions");

    // A template-only creature (no race/class) also composes through the template
    // layer instead of silently dropping it.
    auto templateOnly = std::make_shared<CCreature>();
    auto templateOnlyBase = std::make_shared<CStats>();
    templateOnlyBase->setMainStat("intelligence");
    templateOnlyBase->setIntelligence(6);
    templateOnly->setBaseStats(templateOnlyBase);
    auto boost = std::make_shared<CCreatureTemplate>();
    auto boostStats = std::make_shared<CStats>();
    boostStats->setIntelligence(4);
    boost->setStatAdjustments(boostStats);
    templateOnly->setTemplates({boost});
    expect_true(templateOnly->usesArchetypeComposition(),
                "a creature carrying only a template overlay uses the composed stat path");
    expect_true(templateOnly->getStats()->getIntelligence() == 6 + 4,
                "a template-only creature folds the template adjustments over its own base stats");
    expect_true(templateOnly->getStats()->getMainStat() == "intelligence",
                "a template-only creature keeps its legacy mainStat fallback");
}

void test_creature_templates_do_not_replace_race_or_class() {
    // [EPIC_08][STORY_02][SUBSTORY_01] "Does not replace race/class": attaching a
    // template keeps the race/creatureClass references and their contributions
    // fully intact, and clearing the templates returns the composed stat block
    // bit-identically to the race/class baseline.
    auto interaction = [](const std::string &typeId, const std::string &name) {
        auto action = std::make_shared<CInteraction>();
        action->setType("CInteraction");
        action->setTypeId(typeId);
        action->setName(name);
        return action;
    };

    auto creature = std::make_shared<CCreature>();
    auto base = std::make_shared<CStats>();
    base->setMainStat("strength");
    base->setIntelligence(10);
    creature->setBaseStats(base);

    auto raceBase = std::make_shared<CStats>();
    raceBase->setIntelligence(3);
    auto race = std::make_shared<CCreatureRace>();
    race->setBaseStats(raceBase);
    auto raceClaw = interaction("Claw", "raceClaw");
    race->setActions({raceClaw});
    creature->setRace(race);

    auto classBase = std::make_shared<CStats>();
    classBase->setIntelligence(4);
    auto klass = std::make_shared<CCreatureClass>();
    klass->setMainStat("intelligence");
    klass->setBaseStats(classBase);
    creature->setCreatureClass(klass);

    // Race/class baseline snapshot before any template is attached.
    auto baseline = creature->getStats();

    auto overlay = std::make_shared<CCreatureTemplate>();
    auto overlayStats = std::make_shared<CStats>();
    overlayStats->setIntelligence(5);
    overlay->setStatAdjustments(overlayStats);
    auto empower = interaction("Empower", "templateEmpower");
    overlay->setActions({empower});
    creature->setTemplates({overlay});

    // Identity: the archetype references are untouched by the template layer.
    expect_true(CGameObject::sameInstance(creature->getRace(), race),
                "attaching a template must not replace the race reference");
    expect_true(CGameObject::sameInstance(creature->getCreatureClass(), klass),
                "attaching a template must not replace the creatureClass reference");

    // Contributions: race/class stats and actions remain part of the composition,
    // and the class-authoritative mainStat selection is untouched.
    auto withTemplate = creature->getStats();
    expect_true(withTemplate->getMainStat() == "intelligence",
                "the class mainStat stays authoritative when a template is attached");
    expect_true(withTemplate->getIntelligence() == baseline->getIntelligence() + 5,
                "the template adds exactly its adjustment on top of the intact race/class composition");
    auto effective = creature->getEffectiveInteractions();
    expect_true(effective.find(raceClaw) != effective.end(), "race actions remain exposed when a template is attached");
    expect_true(effective.find(empower) != effective.end(),
                "template actions are added alongside (not instead of) race/class actions");

    // Clearing the templates restores the race/class baseline bit-identically.
    creature->setTemplates({});
    auto restored = creature->getStats();
    expect_true(restored->getMainStat() == baseline->getMainStat(),
                "clearing templates restores the baseline mainStat selection");
    restored->meta()->for_all_properties(restored, [&](auto property) {
        if (property->value_type() != std::type_index(typeid(int))) {
            return;
        }
        expect_true(restored->getProperty<int>(property->name()) == baseline->getProperty<int>(property->name()),
                    "clearing templates should restore the race/class composed stats bit-identically");
    });
}

void test_creature_template_metadata_round_trip() {
    // [EPIC_08][STORY_02][SUBSTORY_01] CCreatureTemplate is a CGameObject-derived
    // metadata definition that serializes like CCreatureRace/CCreatureClass: all of
    // its metadata (stat adjustments, action additions, subtypes, scale adjustment,
    // order, plus inherited label) survives a CSerialization round-trip, it
    // deserializes back into a CCreatureTemplate, its setters are null-safe, and it
    // is never enumerated as a CCreature subtype.
    CTypes::register_type_metadata<CCreatureTemplate, CGameObject>();
    CTypes::register_type_metadata<CStats, CGameObject>();
    CTypes::register_type_metadata<CInteraction, CGameObject>();

    auto game = std::make_shared<CGame>();
    game->getObjectHandler()->registerType(CCreatureTemplate::static_meta()->name(),
                                           []() { return std::make_shared<CCreatureTemplate>(); });
    game->getObjectHandler()->registerType(CStats::static_meta()->name(), []() { return std::make_shared<CStats>(); });
    game->getObjectHandler()->registerType(CInteraction::static_meta()->name(),
                                           []() { return std::make_shared<CInteraction>(); });

    // Neutral defaults: a bare template is a no-op overlay.
    auto fresh = std::make_shared<CCreatureTemplate>();
    expect_true(fresh->getOrder() == 0 && fresh->getScaleAdjustment() == 0,
                "order and scaleAdjustment should default to the neutral 0");
    expect_true(fresh->getStatAdjustments() != nullptr && fresh->getActions().empty() && fresh->getSubtypes().empty(),
                "a fresh template defaults to empty stat adjustments, actions and subtypes");

    auto adjustments = std::make_shared<CStats>();
    adjustments->setStrength(2);
    adjustments->setHit(5);
    auto action = std::make_shared<CInteraction>();
    action->setTypeId("templateEmpower");

    auto overlay = std::make_shared<CCreatureTemplate>();
    overlay->setGame(game);
    overlay->setStatAdjustments(adjustments);
    overlay->setActions({action});
    overlay->setSubtypes({"elite"});
    overlay->setScaleAdjustment(1);
    overlay->setOrder(10);
    overlay->setLabel("Elite");

    auto serialized = CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::serialize(overlay);
    expect_true((*serialized)["class"].get<std::string>() == CCreatureTemplate::static_meta()->name(),
                "a serialized CCreatureTemplate should keep its metadata class identity");

    auto round_trip = std::dynamic_pointer_cast<CCreatureTemplate>(
        CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::deserialize(game, serialized));
    expect_true(round_trip != nullptr,
                "a CCreatureTemplate should deserialize back into a CCreatureTemplate, not a creature or map object");
    expect_true(round_trip->getStatAdjustments() && round_trip->getStatAdjustments()->getStrength() == 2 &&
                    round_trip->getStatAdjustments()->getHit() == 5,
                "stat adjustments should survive the round-trip");
    expect_true(round_trip->getActions().size() == 1, "action additions should survive the round-trip");
    expect_true(round_trip->getSubtypes() == std::set<std::string>({"elite"}),
                "subtypes should survive the round-trip");
    expect_true(round_trip->getScaleAdjustment() == 1, "scaleAdjustment should survive the round-trip");
    expect_true(round_trip->getOrder() == 10, "the ordering key should survive the round-trip");
    expect_true(round_trip->getLabel() == "Elite", "inherited label should survive the round-trip");

    // Null-safety: null stats normalize to a neutral block and null actions drop.
    auto bare = std::make_shared<CCreatureTemplate>();
    bare->setStatAdjustments(nullptr);
    expect_true(bare->getStatAdjustments() != nullptr, "null statAdjustments should normalize to an empty CStats");
    bare->setActions({nullptr});
    expect_true(bare->getActions().empty(), "null actions should be filtered out");

    // A template definition is not a creature subtype, so it must never appear in
    // the CCreature subtype enumeration (random encounters / spawn tables).
    auto creatureSubtypes = game->getObjectHandler()->getAllSubTypes("CCreature");
    expect_true(std::find(creatureSubtypes.begin(), creatureSubtypes.end(), CCreatureTemplate::static_meta()->name()) ==
                    creatureSubtypes.end(),
                "CCreatureTemplate must not be enumerated as a CCreature subtype");
}

void test_no_class_track_creature_composes_bit_identically_to_baseline() {
    // [EPIC_08][STORY_03][SUBSTORY_01] Multiclass class-track records. Neutrality
    // invariant: the track layer is FUTURE-ONLY, and a creature with NO class
    // tracks (every creature on current content) composes bit-identically to the
    // pre-track contracts -- both on the legacy path (no race/class) and on the
    // composed single-class path. Explicitly assigning an empty track set must be
    // exactly as neutral as never touching the property.

    // Legacy creature: same source values as the pinned legacy composition tests.
    auto legacy = std::make_shared<CCreature>();
    auto legacyBase = std::make_shared<CStats>();
    legacyBase->setMainStat("intelligence");
    legacyBase->setIntelligence(10);
    legacyBase->setStrength(4);
    legacyBase->setStamina(6);
    legacy->setBaseStats(legacyBase);
    auto legacyLevelStats = std::make_shared<CStats>();
    legacyLevelStats->setIntelligence(2);
    legacyLevelStats->setStrength(1);
    legacy->setLevelStats(legacyLevelStats);
    const int legacyLevel = 3;
    legacy->setLevel(legacyLevel);

    legacy->setClassTracks({}); // explicit empty set == never configured
    expect_true(legacy->getClassTracks().empty(), "an explicitly empty class-track set stays empty");
    expect_true(!legacy->usesArchetypeComposition(),
                "a creature with no race/class/templates and no class tracks must stay on the legacy stat path");

    auto legacyExpected = std::make_shared<CStats>();
    legacyExpected->setMainStat(legacyBase->getMainStat());
    legacyExpected->addBonus(legacyBase);
    for (int i = 0; i < legacyLevel; ++i) {
        legacyExpected->addBonus(legacyLevelStats);
    }
    auto legacyActual = legacy->getStats();
    expect_true(legacyActual->getMainStat() == legacyExpected->getMainStat(),
                "no-track legacy creature getStats should keep the baseStats mainStat");
    legacyActual->meta()->for_all_properties(legacyActual, [&](auto property) {
        if (property->value_type() != std::type_index(typeid(int))) {
            return;
        }
        expect_true(legacyActual->getProperty<int>(property->name()) ==
                        legacyExpected->getProperty<int>(property->name()),
                    "no-track legacy creature getStats should match the legacy composition bit-identically");
    });

    // Composed creature (race + single class): the single-class path is untouched
    // by the (empty) track layer.
    auto composed = std::make_shared<CCreature>();
    auto composedBase = std::make_shared<CStats>();
    composedBase->setMainStat("strength");
    composedBase->setStrength(4);
    composedBase->setIntelligence(6);
    composed->setBaseStats(composedBase);
    auto raceBase = std::make_shared<CStats>();
    raceBase->setStrength(2);
    raceBase->setStamina(3);
    auto race = std::make_shared<CCreatureRace>();
    race->setBaseStats(raceBase);
    composed->setRace(race);
    auto classBase = std::make_shared<CStats>();
    classBase->setIntelligence(7);
    auto classLevel = std::make_shared<CStats>();
    classLevel->setIntelligence(2);
    auto klass = std::make_shared<CCreatureClass>();
    klass->setMainStat("intelligence");
    klass->setBaseStats(classBase);
    klass->setLevelStats(classLevel);
    composed->setCreatureClass(klass);
    const int composedLevel = 2;
    composed->setLevel(composedLevel);

    composed->setClassTracks({}); // explicit empty set == never configured

    auto composedExpected = std::make_shared<CStats>();
    composedExpected->setMainStat(klass->getMainStat());
    composedExpected->addBonus(raceBase);
    composedExpected->addBonus(classBase);
    composedExpected->addBonus(composedBase);
    for (int i = 0; i < composedLevel; ++i) {
        composedExpected->addBonus(classLevel);
    }
    auto composedActual = composed->getStats();
    expect_true(composedActual->getMainStat() == "intelligence",
                "no-track composed creature keeps the class-authoritative mainStat");
    composedActual->meta()->for_all_properties(composedActual, [&](auto property) {
        if (property->value_type() != std::type_index(typeid(int))) {
            return;
        }
        expect_true(composedActual->getProperty<int>(property->name()) ==
                        composedExpected->getProperty<int>(property->name()),
                    "no-track composed creature getStats should match the single-class composition bit-identically");
    });
    expect_true(composed->getEffectiveInteractions().empty(),
                "an empty class-track set adds no actions to the effective interaction set");
}

void test_creature_class_tracks_fold_deterministically_in_order() {
    // [EPIC_08][STORY_03][SUBSTORY_01] Capability: class tracks are an ORDERED
    // multiclass progression. Stat growth folds each track's class.baseStats and
    // class.levelStats x the TRACK's own level in ascending `order`; track actions
    // merge in the same order (later tracks win duplicate keys, concrete creature
    // actions stay most specific); the first track's class mainStat is
    // authoritative; and the layer coexists with race/racialLevel/templates.
    auto interaction = [](const std::string &typeId, const std::string &name) {
        auto action = std::make_shared<CInteraction>();
        action->setType("CInteraction");
        action->setTypeId(typeId);
        action->setName(name);
        return action;
    };

    auto creature = std::make_shared<CCreature>();
    auto base = std::make_shared<CStats>();
    base->setMainStat("stamina");
    base->setStamina(6);
    base->setStrength(1);
    base->setIntelligence(1);
    creature->setBaseStats(base);
    auto levelStats = std::make_shared<CStats>();
    levelStats->setStamina(1);
    creature->setLevelStats(levelStats);
    const int level = 1;
    creature->setLevel(level);

    // Coexisting layers: race with racial advancement, plus a template overlay.
    auto race = std::make_shared<CCreatureRace>();
    auto raceBase = std::make_shared<CStats>();
    raceBase->setStamina(2);
    race->setBaseStats(raceBase);
    auto racialGrowth = std::make_shared<CStats>();
    racialGrowth->setStamina(3);
    race->setRacialLevelStats(racialGrowth);
    creature->setRace(race);
    const int racialLevel = 2;
    creature->setRacialLevel(racialLevel);

    auto overlay = std::make_shared<CCreatureTemplate>();
    auto overlayStats = std::make_shared<CStats>();
    overlayStats->setStamina(4);
    overlay->setStatAdjustments(overlayStats);
    creature->setTemplates({overlay});

    // Two class tracks with distinct ordering keys; inserted out of order to prove
    // getOrderedClassTracks sorts by the `order` key, not insertion order.
    auto warriorAttack = interaction("Attack", "warriorAttack");
    auto warriorEmpower = interaction("Empower", "warriorEmpower");
    auto warriorCleave = interaction("Cleave", "warriorCleave");
    auto warrior = std::make_shared<CCreatureClass>();
    warrior->setMainStat("strength");
    auto warriorBase = std::make_shared<CStats>();
    warriorBase->setStrength(2);
    warrior->setBaseStats(warriorBase);
    auto warriorGrowth = std::make_shared<CStats>();
    warriorGrowth->setStrength(1);
    warrior->setLevelStats(warriorGrowth);
    warrior->setActions({warriorAttack, warriorEmpower});
    warrior->setLevelling({{"2", warriorCleave}});

    auto mageEmpower = interaction("Empower", "mageEmpower");
    auto mage = std::make_shared<CCreatureClass>();
    mage->setMainStat("intelligence");
    auto mageBase = std::make_shared<CStats>();
    mageBase->setIntelligence(4);
    mage->setBaseStats(mageBase);
    auto mageGrowth = std::make_shared<CStats>();
    mageGrowth->setIntelligence(2);
    mage->setLevelStats(mageGrowth);
    mage->setActions({mageEmpower});

    auto warriorTrack = std::make_shared<CCreatureClassTrack>();
    warriorTrack->setTypeId("warriorTrack");
    warriorTrack->setOrder(10);
    warriorTrack->setCreatureClass(warrior);
    warriorTrack->setLevel(3);

    auto mageTrack = std::make_shared<CCreatureClassTrack>();
    mageTrack->setTypeId("mageTrack");
    mageTrack->setOrder(20);
    mageTrack->setCreatureClass(mage);
    mageTrack->setLevel(2);

    creature->setClassTracks({mageTrack, warriorTrack});
    expect_true(creature->usesArchetypeComposition(), "a creature carrying class tracks uses the composed stat path");

    auto orderedTracks = creature->getOrderedClassTracks();
    expect_true(orderedTracks.size() == 2 && orderedTracks[0] == warriorTrack && orderedTracks[1] == mageTrack,
                "getOrderedClassTracks should sort tracks by ascending order key, not insertion order");

    // Stats: each track folds its class.baseStats plus class.levelStats x its OWN
    // track level; race base, racial advancement, the creature's own base/level
    // growth and the template overlay all keep their documented positions.
    auto stats = creature->getStats();
    expect_true(stats->getStamina() ==
                    2 /*race*/ + 6 /*base*/ + racialLevel * 3 /*racial*/ + level * 1 /*own growth*/ + 4 /*template*/,
                "class tracks must not disturb race/racial/own-growth/template stat sources");
    expect_true(stats->getStrength() == 1 /*base*/ + 2 /*warrior base*/ + 3 * 1 /*warrior growth x track level*/,
                "the first track folds its class base stats and level growth by the track's own level");
    expect_true(stats->getIntelligence() == 1 /*base*/ + 4 /*mage base*/ + 2 * 2 /*mage growth x track level*/,
                "the second track folds its class base stats and level growth by the track's own level");
    expect_true(stats->getMainStat() == "strength",
                "the first track's class mainStat is authoritative over the creature's baseStats mainStat");

    auto effectiveContains = [&creature](const std::shared_ptr<CInteraction> &action) {
        auto effective = creature->getEffectiveInteractions();
        return effective.find(action) != effective.end();
    };

    // Track level unlocks gate on the TRACK's level, not the creature level: the
    // warrior unlock opens at class level 2 while the creature level is only 1.
    expect_true(effectiveContains(warriorCleave),
                "a track's class levelling unlocks gate on the track's own level, not the creature level");
    // Later tracks win duplicate action keys over earlier tracks.
    expect_true(effectiveContains(mageEmpower) && !effectiveContains(warriorEmpower),
                "the later-ordered track should win duplicate action keys between tracks");

    // The ordering key drives the fold-in: pushing the warrior track past the mage
    // track flips both the duplicate-action winner and the authoritative mainStat.
    warriorTrack->setOrder(30);
    expect_true(effectiveContains(warriorEmpower) && !effectiveContains(mageEmpower),
                "changing the order key must change the track application order");
    expect_true(creature->getStats()->getMainStat() == "intelligence",
                "changing the order key must move the mainStat authority to the new first track");
    warriorTrack->setOrder(10);

    // Concrete creature actions stay most specific over track class actions.
    auto concreteAttack = interaction("Attack", "concreteAttack");
    creature->addAction(concreteAttack);
    expect_true(effectiveContains(concreteAttack) && !effectiveContains(warriorAttack),
                "concrete creature actions should stay most specific over track class actions");
}

void test_single_class_track_matches_single_creature_class() {
    // [EPIC_08][STORY_03][SUBSTORY_01] Single-class compatibility: one track
    // referencing class K at level L composes exactly like the legacy single
    // creatureClass = K at creature level L -- stats, mainStat and effective
    // actions. And when tracks and the single creatureClass are BOTH set, the
    // tracks subsume the single class's contributions without replacing the
    // reference.
    auto interaction = [](const std::string &typeId, const std::string &name) {
        auto action = std::make_shared<CInteraction>();
        action->setType("CInteraction");
        action->setTypeId(typeId);
        action->setName(name);
        return action;
    };

    auto classAttack = interaction("Attack", "classAttack");
    auto classUnlock = interaction("Cleave", "classUnlock");
    auto klass = std::make_shared<CCreatureClass>();
    klass->setMainStat("intelligence");
    auto classBase = std::make_shared<CStats>();
    classBase->setIntelligence(4);
    classBase->setStamina(1);
    klass->setBaseStats(classBase);
    auto classGrowth = std::make_shared<CStats>();
    classGrowth->setIntelligence(2);
    klass->setLevelStats(classGrowth);
    klass->setActions({classAttack});
    klass->setLevelling({{"2", classUnlock}});

    const int level = 2;
    auto makeCreature = [&level]() {
        auto creature = std::make_shared<CCreature>();
        auto base = std::make_shared<CStats>();
        base->setMainStat("strength");
        base->setStrength(5);
        base->setIntelligence(10);
        creature->setBaseStats(base);
        auto growth = std::make_shared<CStats>();
        growth->setIntelligence(1);
        creature->setLevelStats(growth);
        creature->setLevel(level);
        return creature;
    };

    // Baseline: legacy single creatureClass at creature level 2.
    auto single = makeCreature();
    single->setCreatureClass(klass);

    // Equivalent: one class track (same class, track level == creature level).
    auto track = std::make_shared<CCreatureClassTrack>();
    track->setCreatureClass(klass);
    track->setLevel(level);
    auto tracked = makeCreature();
    tracked->setClassTracks({track});

    auto singleStats = single->getStats();
    auto trackedStats = tracked->getStats();
    expect_true(trackedStats->getMainStat() == singleStats->getMainStat(),
                "a single class track selects the same authoritative mainStat as the single creatureClass");
    trackedStats->meta()->for_all_properties(trackedStats, [&](auto property) {
        if (property->value_type() != std::type_index(typeid(int))) {
            return;
        }
        expect_true(trackedStats->getProperty<int>(property->name()) == singleStats->getProperty<int>(property->name()),
                    "a single class track composes stats identically to the same single creatureClass");
    });

    auto actionKeys = [](const std::shared_ptr<CCreature> &creature) {
        std::set<std::string> keys;
        for (const auto &action : creature->getEffectiveInteractions()) {
            keys.insert(action->getTypeId());
        }
        return keys;
    };
    expect_true(actionKeys(tracked) == actionKeys(single),
                "a single class track exposes the same effective actions (starting + level unlocks) as the single "
                "creatureClass");
    expect_true(actionKeys(tracked).count("Cleave") == 1,
                "the class level unlock is exposed in both the single-class and single-track compositions");

    // Precedence when both are set: non-empty tracks subsume the single class's
    // contributions -- setting an additional single creatureClass changes nothing
    // -- while the reference itself is preserved, not replaced.
    auto other = std::make_shared<CCreatureClass>();
    other->setMainStat("stamina");
    auto otherBase = std::make_shared<CStats>();
    otherBase->setStamina(50);
    other->setBaseStats(otherBase);
    tracked->setCreatureClass(other);

    auto subsumedStats = tracked->getStats();
    expect_true(subsumedStats->getMainStat() == singleStats->getMainStat(),
                "non-empty tracks keep mainStat authority over an additionally set single creatureClass");
    subsumedStats->meta()->for_all_properties(subsumedStats, [&](auto property) {
        if (property->value_type() != std::type_index(typeid(int))) {
            return;
        }
        expect_true(subsumedStats->getProperty<int>(property->name()) ==
                        singleStats->getProperty<int>(property->name()),
                    "non-empty tracks subsume the single creatureClass stat contributions entirely");
    });
    expect_true(CGameObject::sameInstance(tracked->getCreatureClass(), other),
                "the single creatureClass reference is preserved (not replaced) when tracks are present");
}

void test_same_order_class_tracks_tie_break_deterministically() {
    // [EPIC_08][STORY_03][SUBSTORY_01] Determinism for equal `order` keys: the
    // tie-break chain exhausts every stable configured field before touching names
    // -- track typeId, then referenced-class typeId, then per-track level -- so
    // same-order tracks never fall to the backing set's pointer order. Each case
    // asserts the fold order for BOTH insertion orders of the same two records.
    auto orderedFor = [](const std::shared_ptr<CCreatureClassTrack> &a, const std::shared_ptr<CCreatureClassTrack> &b) {
        auto creature = std::make_shared<CCreature>();
        creature->setClassTracks({a, b});
        auto forward = creature->getOrderedClassTracks();
        creature->setClassTracks({b, a});
        auto reversed = creature->getOrderedClassTracks();
        expect_true(forward.size() == 2 && reversed.size() == 2 && forward[0] == reversed[0] &&
                        forward[1] == reversed[1],
                    "same-order tracks must sort identically regardless of insertion order");
        return forward;
    };

    // Case 1: equal order, distinct track typeIds -- the track typeId decides.
    auto klass = std::make_shared<CCreatureClass>();
    klass->setTypeId("warriorClass");
    auto trackA = std::make_shared<CCreatureClassTrack>();
    trackA->setTypeId("aTrack");
    trackA->setCreatureClass(klass);
    auto trackB = std::make_shared<CCreatureClassTrack>();
    trackB->setTypeId("bTrack");
    trackB->setCreatureClass(klass);
    auto byTypeId = orderedFor(trackA, trackB);
    expect_true(byTypeId.size() == 2 && byTypeId[0] == trackA && byTypeId[1] == trackB,
                "equal-order tracks tie-break on the track typeId first");

    // Case 2: equal order, anonymous tracks, distinct class typeIds -- the
    // referenced class's typeId decides.
    auto mage = std::make_shared<CCreatureClass>();
    mage->setTypeId("mageClass");
    mage->setMainStat("intelligence");
    auto warrior = std::make_shared<CCreatureClass>();
    warrior->setTypeId("warriorClass");
    warrior->setMainStat("strength");
    auto mageTrack = std::make_shared<CCreatureClassTrack>();
    mageTrack->setCreatureClass(mage);
    auto warriorTrack = std::make_shared<CCreatureClassTrack>();
    warriorTrack->setCreatureClass(warrior);
    auto byClass = orderedFor(mageTrack, warriorTrack);
    expect_true(byClass.size() == 2 && byClass[0] == mageTrack && byClass[1] == warriorTrack,
                "anonymous equal-order tracks tie-break on the referenced class typeId");
    // The stable tie-break drives observable composition: the first track's class
    // mainStat is authoritative for both insertion orders.
    auto creature = std::make_shared<CCreature>();
    auto base = std::make_shared<CStats>();
    base->setMainStat("stamina");
    creature->setBaseStats(base);
    creature->setClassTracks({warriorTrack, mageTrack});
    expect_true(creature->getStats()->getMainStat() == "intelligence",
                "mainStat authority follows the deterministic tie-break, not insertion or pointer order");

    // Case 3: equal order, anonymous tracks of the SAME class -- the per-track
    // level decides (ascending), keeping the fold reproducible; and because the
    // class is the same, either relative order composes identical stats anyway.
    auto low = std::make_shared<CCreatureClassTrack>();
    low->setCreatureClass(warrior);
    low->setLevel(1);
    auto high = std::make_shared<CCreatureClassTrack>();
    high->setCreatureClass(warrior);
    high->setLevel(3);
    auto byLevel = orderedFor(low, high);
    expect_true(byLevel.size() == 2 && byLevel[0] == low && byLevel[1] == high,
                "same-class equal-order tracks tie-break on the per-track level");
}

void test_creature_class_track_metadata_round_trip() {
    // [EPIC_08][STORY_03][SUBSTORY_01] CCreatureClassTrack is a CGameObject-derived
    // record that serializes like the other archetype definitions: its class
    // reference, per-track level and ordering key (plus inherited label) survive a
    // CSerialization round-trip, it deserializes back into a CCreatureClassTrack,
    // and it is never enumerated as a CCreature subtype.
    CTypes::register_type_metadata<CCreatureClassTrack, CGameObject>();
    CTypes::register_type_metadata<CCreatureClass, CGameObject>();
    CTypes::register_type_metadata<CStats, CGameObject>();
    CTypes::register_type_metadata<CInteraction, CGameObject>();

    auto game = std::make_shared<CGame>();
    game->getObjectHandler()->registerType(CCreatureClassTrack::static_meta()->name(),
                                           []() { return std::make_shared<CCreatureClassTrack>(); });
    game->getObjectHandler()->registerType(CCreatureClass::static_meta()->name(),
                                           []() { return std::make_shared<CCreatureClass>(); });
    game->getObjectHandler()->registerType(CStats::static_meta()->name(), []() { return std::make_shared<CStats>(); });
    game->getObjectHandler()->registerType(CInteraction::static_meta()->name(),
                                           []() { return std::make_shared<CInteraction>(); });

    // Neutral defaults: a bare track is a no-op record.
    auto fresh = std::make_shared<CCreatureClassTrack>();
    expect_true(fresh->getLevel() == 0 && fresh->getOrder() == 0, "level and order should default to the neutral 0");
    expect_true(fresh->getCreatureClass() == nullptr,
                "a fresh track carries no class reference (a null class contributes nothing)");

    auto klass = std::make_shared<CCreatureClass>();
    klass->setMainStat("strength");
    auto classBase = std::make_shared<CStats>();
    classBase->setStrength(3);
    klass->setBaseStats(classBase);

    auto track = std::make_shared<CCreatureClassTrack>();
    track->setGame(game);
    track->setCreatureClass(klass);
    track->setLevel(3);
    track->setOrder(10);
    track->setLabel("Warrior track");

    auto serialized = CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::serialize(track);
    expect_true((*serialized)["class"].get<std::string>() == CCreatureClassTrack::static_meta()->name(),
                "a serialized CCreatureClassTrack should keep its record class identity");

    auto round_trip = std::dynamic_pointer_cast<CCreatureClassTrack>(
        CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::deserialize(game, serialized));
    expect_true(round_trip != nullptr,
                "a CCreatureClassTrack should deserialize back into a CCreatureClassTrack, not a creature");
    expect_true(round_trip->getCreatureClass() != nullptr &&
                    round_trip->getCreatureClass()->getMainStat() == "strength",
                "the class reference (and its mainStat identity) should survive the round-trip");
    expect_true(round_trip->getCreatureClass()->getBaseStats() &&
                    round_trip->getCreatureClass()->getBaseStats()->getStrength() == 3,
                "the referenced class's base stats should survive the round-trip");
    expect_true(round_trip->getLevel() == 3, "the per-track level should survive the round-trip");
    expect_true(round_trip->getOrder() == 10, "the ordering key should survive the round-trip");
    expect_true(round_trip->getLabel() == "Warrior track", "inherited label should survive the round-trip");

    // A track record is not a creature subtype, so it must never appear in the
    // CCreature subtype enumeration (random encounters / spawn tables).
    auto creatureSubtypes = game->getObjectHandler()->getAllSubTypes("CCreature");
    expect_true(std::find(creatureSubtypes.begin(), creatureSubtypes.end(),
                          CCreatureClassTrack::static_meta()->name()) == creatureSubtypes.end(),
                "CCreatureClassTrack must not be enumerated as a CCreature subtype");
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

// getDmg(allowCrit) gates whether a rolled critical is applied. Interactions that must
// never crit (e.g. Devour) pass allowCrit=false; the crit die is still consumed so the RNG
// stream is identical either way. With hit=100 and crit=100 every swing connects and would
// crit, so the flag deterministically decides between the doubled and un-doubled damage.
void test_creature_get_dmg_allow_crit_flag_gates_the_crit_double() {
    srand(20260701u);
    auto stats = std::make_shared<CStats>();
    stats->setMainStat("intelligence");
    stats->setHit(100);  // always connects
    stats->setCrit(100); // would always crit when crit is allowed
    stats->setDmgMin(5);
    stats->setDmgMax(5); // fixed base damage of exactly 5
    stats->setDamage(0);
    auto creature = std::make_shared<CCreature>();
    creature->setBaseStats(stats);
    creature->setLevelStats(std::make_shared<CStats>());
    creature->setLevel(0); // getStats() == baseStats: no level/equipment/effect bonuses

    for (int i = 0; i < 50; ++i) {
        expect_true(creature->getDmg(true) == 10, "with crit allowed a guaranteed crit doubles 5 to 10");
        expect_true(creature->getDmg(false) == 5, "with crit disallowed the same guaranteed-hit swing stays at 5");
    }
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

// healProc/addManaProc convert a percentage into an absolute restore amount, while
// heal(0)/addMana(0) are the documented "restore to full" sentinels. A positive
// percentage whose truncated amount is 0 (small percent and/or a low maximum) must
// restore exactly 1 point instead of collapsing into the sentinel; an explicit 0
// percentage keeps the full-restore call relied upon by existing callers.
void test_proc_restores_clamp_positive_percentages_away_from_full_restore_sentinel() {
    auto creature = std::make_shared<CCreature>();
    creature->setBaseStats(stats_with_main(1, 1)); // hpMax = manaMax = 7

    creature->setHp(3);
    creature->healProc(2); // 2% of 7 truncates to 0
    expect_true(creature->getHp() == 4, "a positive heal percentage must restore at least 1 hp, never heal to full");

    creature->healProc(0);
    expect_true(creature->getHp() == 7, "healProc(0) must keep the restore-to-full sentinel behavior");

    creature->setHp(3);
    creature->healProc(100);
    expect_true(creature->getHp() == 7, "healProc(100) must still restore to full hp");

    creature->setMana(2);
    creature->addManaProc(4); // 4% of 7 truncates to 0
    expect_true(creature->getMana() == 3,
                "a positive mana percentage must restore at least 1 mana, never restore to full");

    creature->addManaProc(0);
    expect_true(creature->getMana() == 7, "addManaProc(0) must keep the restore-to-full sentinel behavior");
}

} // namespace

int main() {
    pybind11::scoped_interpreter guard{};
    test_signal_slots_fail_closed_on_bad_config();
    test_dynamic_property_cannot_spoof_typed_engine_signal();
    test_typed_engine_signal_still_fires_directly();
    test_effect_applies_for_exactly_its_duration_without_underflow();
    test_proc_restores_clamp_positive_percentages_away_from_full_restore_sentinel();
    test_creature_get_dmg_allow_crit_flag_gates_the_crit_double();
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
    test_equip_item_same_instance_is_noop_and_keeps_cursed_lock();
    test_no_archetype_creature_stats_keep_legacy_composition();
    test_creature_stat_precedence_orders_sources_and_main_stat();
    test_racial_progression_defaults_keep_composition_neutral();
    test_racial_level_composes_race_progression_independently_of_class_level();
    test_racial_level_round_trips_through_meta_property_binding();
    test_creature_class_main_stat_is_authoritative_over_race();
    test_player_composed_stats_reflect_race_and_class_archetype();
    test_player_without_archetype_falls_back_to_base_stats();
    test_no_template_creature_composes_bit_identically_to_baseline();
    test_creature_templates_compose_after_race_and_class_in_order();
    test_creature_templates_do_not_replace_race_or_class();
    test_creature_template_metadata_round_trip();
    test_no_class_track_creature_composes_bit_identically_to_baseline();
    test_creature_class_tracks_fold_deterministically_in_order();
    test_single_class_track_matches_single_creature_class();
    test_same_order_class_tracks_tie_break_deterministically();
    test_creature_class_track_metadata_round_trip();
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
