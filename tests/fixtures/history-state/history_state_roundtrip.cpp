// Copyright (C) 2026 Andrzej Lis
// SPDX-License-Identifier: GPL-3.0-or-later

#include <QApplication>
#include <QGraphicsScene>
#include <buildings/teleporter.h>
#include <configuration/configurationprovider.h>
#include <creatures/creature.h>
#include <items/armor.h>
#include <items/weapon.h>
#include <map/map.h>
#include <stats/stats.h>
#include <cstdlib>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>

void registerMetaTypes();

namespace {
void require(bool condition, const char *message) {
    if (!condition)
        throw std::runtime_error(message);
}

std::map<int, std::string> equipmentNames(Creature &creature) {
    std::map<int, std::string> result;
    for (const auto &entry : *creature.getEquipped())
        if (entry.second)
            result[entry.first] = entry.second->className;
    return result;
}

void checkEquipment(Creature &creature, const std::string &template_name) {
    const std::map<int, std::string> expected = equipmentNames(creature);
    require(!expected.empty(), "Equipment fixture has no equipped items");
    const Json::Value stats = creature.getStats()->saveToJson();
    const Json::Value saved = creature.saveToJson();
    require(saved["equipment"].isObject(), "Slot-map save did not record equipment");
    Creature loaded(template_name, saved);
    require(equipmentNames(loaded) == expected, "Loading the save changed equipped slot identities");
    require(loaded.getStats()->saveToJson() == stats, "Loading the save changed actual equipment stat bonuses");
    const Json::Value equipment_config = *ConfigurationProvider::getConfig("config/slots.json");
    for (const std::string &key : equipment_config.getMemberNames())
        require(loaded.getEquipped()->count(std::atoi(key.c_str())) == 1,
                "Loading omitted an actual declared equipment slot");
    require(loaded.saveToJson() == saved, "Saving after loading changed persisted creature state");
}

void equipmentRegression(const std::string &template_name) {
    Creature creature(template_name);
    Weapon *weapon = 0;
    Armor *armor = 0;
    Json::Value items = *ConfigurationProvider::getConfig("config/items.json");
    for (const std::string &key : items.getMemberNames()) {
        const std::string type = items[key].get("class", "").asString();
        if (!weapon && type == "Weapon")
            weapon = dynamic_cast<Weapon *>(Item::getItem(key));
        if (!armor && type == "Armor")
            armor = dynamic_cast<Armor *>(Item::getItem(key));
    }
    require(weapon && armor, "Original item factory could not construct the weapon/armor fixture");
    creature.setWeapon(weapon);
    creature.setArmor(armor);
    require(creature.getWeapon() == weapon && creature.getArmor() == armor,
            "Original equipment accessors did not expose the fixture items");
    checkEquipment(creature, template_name);
    creature.setWeapon(0);
    require(!creature.hasEquipped(weapon), "Unequipping left the weapon in an actual equipment slot");
    checkEquipment(creature, template_name);
    creature.setWeapon(weapon);
    creature.setArmor(0);
    require(!creature.hasEquipped(armor), "Unequipping left the armor in an actual equipment slot");
    checkEquipment(creature, template_name);
}

std::set<std::string> teleporterPositions(Map &map) {
    std::set<std::string> result;
    Json::FastWriter writer;
    for (MapObject *object : *map.getObjects()) {
        Teleporter *teleporter = dynamic_cast<Teleporter *>(object);
        if (!teleporter)
            continue;
        require(teleporter->getMap() == &map, "Loaded Teleporter has no actual map ownership");
        Json::Value coords(Json::arrayValue);
        coords.append(teleporter->getPosX());
        coords.append(teleporter->getPosY());
        coords.append(teleporter->getPosZ());
        result.insert(writer.write(coords));
    }
    return result;
}

void mapTransferRegression() {
    QGraphicsScene scene;
    Map map(&scene);
    Item *item = 0;
    Json::Value items = *ConfigurationProvider::getConfig("config/items.json");
    for (const std::string &key : items.getMemberNames()) {
        if (items[key].get("class", "").asString() == "Weapon") {
            item = Item::getItem(key);
            break;
        }
    }
    require(item, "Original item factory could not construct transfer fixture");
    bool destroyed = false;
    QObject::connect(item, &QObject::destroyed, [&destroyed]() { destroyed = true; });
    map.addObject(item);
    require(map.getObjects()->count(item) == 1 && item->scene() == &scene, "Map did not own the real transfer fixture");
    map.removeObject(item);
    require(!destroyed, "Removing an item deleted it before genuine inventory transfer");
    require(map.getObjects()->count(item) == 0 && item->scene() == 0, "Removing an item left map or scene membership");
    Creature player("Sorcerer");
    player.addItem(item);
    require(player.getInventory()->count(item) == 1, "Detached item could not enter actual creature inventory");
}

void teleporterRegression() {
    QGraphicsScene scene;
    Map map(&scene);
    Json::Value config;
    config["map"]["default"]["0"] = "GrassTile";
    Json::Value first(Json::arrayValue), second(Json::arrayValue);
    first.append(31);
    first.append(32);
    first.append(0);
    second.append(34);
    second.append(35);
    second.append(1);
    config["state"]["Teleporter"]["Teleporter"].append(first);
    config["state"]["Teleporter"]["Teleporter"].append(second);
    map.loadFromJson(config);
    const auto positions = teleporterPositions(map);
    require(positions.size() == 2, "Map did not construct both real Teleporter actors from saved state");
    const Json::Value saved = map.saveToJson();
    require(saved["state"]["Teleporter"]["Teleporter"].size() == 2, "Map save omitted a real Teleporter actor");
    QGraphicsScene restored_scene;
    Map restored(&restored_scene);
    restored.loadFromJson(saved);
    require(teleporterPositions(restored) == positions, "Teleporter map load/save changed actual actor coordinates");
}
} // namespace

int main(int argc, char **argv) {
    QApplication application(argc, argv);
    try {
        registerMetaTypes();
        mapTransferRegression();
        equipmentRegression(argc > 1 ? argv[1] : "Sorcerer");
        teleporterRegression();
        std::cout
            << "{\"status\":\"success\",\"checks\":{\"mapInventoryTransfer\":true,\"equipmentAndStatsRoundtrip\":true,"
               "\"unequippedSlotsRoundtrip\":true,\"realTeleporterActorsRoundtrip\":true}}\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
