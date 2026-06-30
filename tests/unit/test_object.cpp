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
#include "object/CDialog.h"
#include "object/CEffect.h"
#include "object/CGameObject.h"
#include "object/CItem.h"
#include "object/CMapObject.h"
#include "object/CMarket.h"
#include "object/CPlayer.h"
#include "object/CQuest.h"
#include "object/CTile.h"
#include "test_harness.h"
#include "vutil.h"

#include <limits>
#include <map>
#include <memory>
#include <set>
#include <string>
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

void test_creature_archetype_identity_accessors_use_fallbacks() {
    auto creature = std::make_shared<CCreature>();

    creature->setTypeId("Pritz");
    creature->setName("pritz_instance_1");
    creature->setLabel("Pritz Footsoldier");
    expect_true(creature->getRaceId() == "Pritz", "race id should prefer the configured type id");
    expect_true(creature->getCreatureClassId() == "Pritz", "creature class id should prefer the configured type id");
    expect_true(creature->getRaceLabel() == "Pritz Footsoldier", "race label should prefer the configured label");
    expect_true(creature->getCreatureClassLabel() == "Pritz Footsoldier",
                "creature class label should prefer the configured label");

    auto without_type = std::make_shared<CCreature>();
    without_type->setName("nameless_horror");
    without_type->setLabel("Nameless Horror");
    expect_true(without_type->getRaceId() == "nameless_horror",
                "race id should fall back to name when type id is empty");
    expect_true(without_type->getCreatureClassId() == "nameless_horror",
                "creature class id should fall back to name when type id is empty");
    expect_true(without_type->getRaceLabel() == "Nameless Horror",
                "race label should prefer label even without a type id");
    expect_true(without_type->getCreatureClassLabel() == "Nameless Horror",
                "creature class label should prefer label even without a type id");

    auto identity_only = std::make_shared<CCreature>();
    identity_only->setTypeId("Gooby");
    identity_only->setName("the_dreaded_gooby");
    expect_true(identity_only->getRaceLabel() == "Gooby", "race label should fall back to race id when label is empty");
    expect_true(identity_only->getCreatureClassLabel() == "Gooby",
                "creature class label should fall back to creature class id when label is empty");

    auto bare = std::make_shared<CCreature>();
    bare->setName("lonely_actor");
    expect_true(bare->getRaceLabel() == "lonely_actor",
                "race label should fall back through race id to name when nothing else is set");
    expect_true(bare->getCreatureClassLabel() == "lonely_actor",
                "creature class label should fall back through creature class id to name when nothing else is set");
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

} // namespace

int main() {
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
    test_creature_archetype_identity_accessors_use_fallbacks();
    test_game_object_comparator_and_identity_sets_document_current_semantics();
    test_game_object_named_comparison_helpers_cover_explicit_semantics();

    return finish_tests();
}
