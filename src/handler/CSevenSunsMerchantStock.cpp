// Copyright (C) 2026 Andrzej Lis
// SPDX-License-Identifier: GPL-3.0-or-later
#include "handler/CSevenSunsMerchantStock.h"
#include "handler/CSevenSunsMerchantStockData.h"
#include "core/CController.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CMap.h"
#include "core/CSceneManager.h"
#include "core/CStats.h"
#include "handler/CObjectHandler.h"
#include "object/CCreature.h"
#include "object/CInteraction.h"
#include "object/CItem.h"
#include "veventloop.h"

#include <algorithm>
#include <any>
#include <charconv>
#include <stdexcept>
#include <string_view>
#include <typeinfo>

namespace seven_suns_merchant_stock_detail {
namespace {
constexpr auto StockKey = "plugin_citySevenSunsStock";
constexpr auto ActorId = "citySevenSunsRevealedDoppss";
constexpr auto WeaponId = "citySevenSunsDoppssWeapon";
constexpr auto WeaponSha = "44c02f993700e11ec0994567ad9edb9ad4c1737eab6761dbe6767887f6cc343a";
constexpr auto CreatureSha = "3a94bcb25ad1dccf2f0b78dcafe1529e57802a69b566bf8aa566e7c74c8ceee1";

void require(bool value, const char *message) {
    if (!value)
        throw std::runtime_error(message);
}

std::string sourceActor(const std::string &lineage, const std::string &area) {
    if (area == "AR0601" && lineage == "cityAr0601Actor1")
        return "AR0601#actor1";
    if (area == "AR0601" && lineage == "cityAr0601Actor3")
        return "AR0601#actor3";
    if (area == "AR0602" && lineage == "cityAr0602Actor1")
        return "AR0602#actor1";
    if (area == "AR0602" && lineage == "cityAr0602Actor2")
        return "AR0602#actor2";
    throw std::runtime_error("Unknown Seven Suns replacement lineage or source floor");
}

std::string encode(const json &value) { return "city-json:" + value.dump(); }

template <typename T> T stored(const std::shared_ptr<CGameObject> &owner, const std::string &key) {
    require(owner != nullptr, "Missing Seven Suns stock metadata owner");
    const auto &type = typeid(*owner);
    const auto metadata = type == typeid(CCreature) ? CCreature::static_meta()
                          : type == typeid(CWeapon) ? CWeapon::static_meta()
                          : type == typeid(CItem)   ? CItem::static_meta()
                                                    : nullptr;
    require(metadata != nullptr, "Unsupported Seven Suns stock metadata owner");
    const auto property = metadata->find_property(key, owner);
    using Slot = vstd::detail::dynamic_property_impl<CGameObject, T>;
    require(property && typeid(*property) == typeid(Slot), "Seven Suns stock requires ordinary typed metadata");
    return std::any_cast<T>(static_cast<const Slot &>(*property).get(std::any{}));
}

bool keys(const json &value, std::initializer_list<const char *> names) {
    if (!value.is_object() || value.size() != names.size())
        return false;
    return std::ranges::all_of(names, [&](const char *name) { return value.contains(name); });
}

int integer(const json &value) {
    require(value.is_number_integer(), "Seven Suns stock requires an ordinary integer");
    const auto encoded = value.dump();
    int result = 0;
    const auto parsed = std::from_chars(encoded.data(), encoded.data() + encoded.size(), result);
    require(parsed.ec == std::errc{} && parsed.ptr == encoded.data() + encoded.size(),
            "Seven Suns stock integer exceeds its native range");
    return result;
}

bool sameValue(const json &actual, const json &expected) {
    if (expected.is_object()) {
        if (!actual.is_object() || actual.size() != expected.size())
            return false;
        for (const auto &[key, value] : expected.items())
            if (!actual.contains(key) || !sameValue(actual.at(key), value))
                return false;
        return true;
    }
    if (expected.is_array()) {
        if (!actual.is_array() || actual.size() != expected.size())
            return false;
        for (std::size_t index = 0; index < expected.size(); ++index)
            if (!sameValue(actual.at(index), expected.at(index)))
                return false;
        return true;
    }
    if (expected.is_number_integer())
        return actual.is_number_integer() && actual.dump() == expected.dump();
    if (expected.is_boolean())
        return actual.is_boolean() && actual.get<bool>() == expected.get<bool>();
    if (expected.is_string())
        return actual.is_string() && actual.get<std::string>() == expected.get<std::string>();
    return expected.is_null() && actual.is_null();
}

json chargesDocument(const std::string &encoded) {
    constexpr std::string_view prefix = "city-json:";
    require(encoded.size() <= 64 && encoded.starts_with(prefix), "Malformed Seven Suns charge storage");
    const auto value = json::parse(std::string_view(encoded).substr(prefix.size()));
    require(value.is_array() && value.size() == 3, "Malformed Seven Suns charge count");
    for (const auto &charge : value) {
        const auto count = integer(charge);
        require(count >= 0 && count <= 65535, "Seven Suns charges exceed source capacity");
    }
    return value;
}

const seven_suns_stock::Item &itemDefinition(std::string_view code) {
    auto found = std::ranges::find_if(seven_suns_stock::Items, [&](const auto &value) { return value.code == code; });
    require(found != seven_suns_stock::Items.end(), "Unknown concrete Seven Suns treasure item");
    return *found;
}

json outcome(const char *kind, std::string code = {}, int quantity = 0, int gold = 0, std::array<int, 3> charges = {}) {
    return json{{"kind", kind},
                {"code", std::move(code)},
                {"quantity", quantity},
                {"gold", gold},
                {"charges", json::array({charges[0], charges[1], charges[2]})}};
}

json resolve(const std::function<int()> &draw) {
    std::string family = "RNDTRE05";
    json trace = json::array();
    for (int depth = 0; depth < 3; ++depth) {
        auto found =
            std::ranges::find_if(seven_suns_stock::Rows, [&](const auto &value) { return value.family == family; });
        require(found != seven_suns_stock::Rows.end(), "Unknown Seven Suns random family");
        const int column = draw();
        require(column >= 1 && column <= 20, "Seven Suns native stock roll must be1..20");
        const std::string token(found->cells[column - 1]);
        trace[trace.size()] = json{{"family", family}, {"row", found->ordinal}, {"column", column}, {"token", token}};
        if (token.empty())
            return json{{"rolls", trace}, {"outcome", outcome("none")}};
        if (std::ranges::any_of(seven_suns_stock::Rows, [&](const auto &value) { return value.family == token; })) {
            family = token;
            continue;
        }
        if (std::ranges::all_of(token, [](char value) { return value >= '0' && value <= '9'; })) {
            const int gold = std::stoi(token);
            require(gold >= 0 && gold <= 256, "Seven Suns gold exceeds finite source conversion");
            return json{{"rolls", trace}, {"outcome", outcome("gold", {}, 0, gold)}};
        }
        const auto separator = token.find('*');
        const auto code = token.substr(0, separator);
        const auto &item = itemDefinition(code);
        const int quantity =
            separator != std::string::npos && item.stackSize > 1 ? std::stoi(token.substr(separator + 1)) : 1;
        require(quantity >= 1 && quantity <= std::max(1, item.stackSize), "Seven Suns stack exceeds source capacity");
        return json{{"rolls", trace}, {"outcome", outcome("item", code, quantity, 0, item.charges)}};
    }
    throw std::runtime_error("Seven Suns random-stock depth exceeded");
}

json profile() {
    return json{{"hpMax", 28},  {"initialHp", 28}, {"mana", 0},   {"killXp", 420}, {"dmgMin", 1},
                {"dmgMax", 12}, {"hit", 75},       {"damage", 0}, {"crit", 0}};
}

json expectedOwned(const std::string &lineage, const json &selected) {
    json owned = json::array();
    owned[owned.size()] =
        json{{"role", "weapon"}, {"name", lineage + "NativeWeapon"},  {"resourceId", WeaponId}, {"sourceCode", "S1-12"},
             {"quantity", 1},    {"charges", json::array({0, 0, 0})}, {"undroppable", true}};
    if (selected.at("kind").get<std::string>() == "item") {
        const auto &item = itemDefinition(selected.at("code").get<std::string>());
        owned[owned.size()] = json{{"role", "treasure"},
                                   {"name", lineage + "NativeTreasure"},
                                   {"resourceId", std::string(item.resourceId)},
                                   {"sourceCode", std::string(item.code)},
                                   {"quantity", selected.at("quantity")},
                                   {"charges", json::array({item.charges[0], item.charges[1], item.charges[2]})},
                                   {"undroppable", !(item.flags & 4)}};
    }
    return owned;
}

json certificate(const std::string &lineage, const std::string &area, const json &selection) {
    return json{{"version", 1},
                {"lineage", lineage},
                {"area", area},
                {"creature", "DOPPSS"},
                {"creatureFingerprint", CreatureSha},
                {"weaponBaseFingerprint", WeaponSha},
                {"rolls", selection.at("rolls")},
                {"outcome", selection.at("outcome")},
                {"owned", expectedOwned(lineage, selection.at("outcome"))},
                {"native", profile()},
                {"originalParity", false},
                {"itemAbilitiesEstablished", false},
                {"nativeDiceRule", "oneNativeD20PerSelectedRow"},
                {"sourceScheduleRaw", 4294967295ULL}};
}

void validateCertificate(const json &receipt, const std::string &lineage, const std::string &area) {
    require(encode(receipt).size() <= 8192 &&
                keys(receipt, {"version", "lineage", "area", "creature", "creatureFingerprint", "weaponBaseFingerprint",
                               "rolls", "outcome", "owned", "native", "originalParity", "itemAbilitiesEstablished",
                               "nativeDiceRule", "sourceScheduleRaw"}),
            "Malformed Seven Suns stock certificate");
    const auto &rolls = receipt.at("rolls");
    require(rolls.is_array() && !rolls.empty() && rolls.size() <= 3, "Malformed Seven Suns stock roll history");
    std::size_t offset = 0;
    const auto selection = resolve([&] {
        require(offset < rolls.size(), "Missing Seven Suns stock roll history");
        const auto &row = rolls.at(offset++);
        require(keys(row, {"family", "row", "column", "token"}), "Malformed Seven Suns stock roll row");
        return integer(row.at("column"));
    });
    require(offset == rolls.size() && sameValue(receipt, certificate(lineage, area, selection)),
            "Seven Suns stock certificate does not match its finite source replay");
}

template <typename T>
void put(const std::shared_ptr<CGameObject> &object, const std::string &key, T value,
         const std::function<void()> &check) {
    check();
    object->setProperty<T>(key, std::move(value));
    check();
}

void itemProperties(const std::shared_ptr<CItem> &item, const std::shared_ptr<CGame> &game, const std::string &lineage,
                    const std::string &role, const std::string &code, const std::string &resourceId, int quantity,
                    const std::array<int, 3> &charges, int flags, int itemType, int price, int lore, int stack,
                    int enchantment, const std::string &fingerprint, const std::string &label,
                    const std::string &animation, bool weapon, const std::function<void()> &check) {
    check();
    item->setGame(game);
    check();
    item->setType(weapon ? "CWeapon" : "CItem");
    item->setTypeId(resourceId);
    item->setName(lineage + (weapon ? "NativeWeapon" : "NativeTreasure"));
    item->setLabel(label);
    item->setAnimation(animation);
    check();
    put(item, "plugin_citySourceItem", code, check);
    put(item, "plugin_citySourceItemFingerprint", fingerprint, check);
    put(item, "plugin_citySourceItemFlags", flags, check);
    put(item, "plugin_citySourceEnchantment", enchantment, check);
    put(item, "plugin_citySourceFlags", 0, check);
    put(item, "plugin_cityItemType", itemType, check);
    put(item, "plugin_cityValue", price, check);
    put(item, "plugin_cityLore", lore, check);
    put(item, "plugin_cityStackSize", stack, check);
    put(item, "plugin_cityQuantity", quantity, check);
    put(item, "plugin_cityCharges", encode(json::array({charges[0], charges[1], charges[2]})), check);
    put(item, "plugin_cityUndroppable", weapon || !(flags & 4), check);
    put(item, "plugin_cityUnstealable", weapon, check);
    put(item, "plugin_cityTradeable", !weapon && bool(flags & 4), check);
    put(item, "plugin_cityUnidentified", !weapon, check);
    put(item, "plugin_cityAbilitiesPending", !weapon, check);
    put(item, "plugin_cityStockLineage", lineage, check);
    put(item, "plugin_cityStockKind", role, check);
}

json ownedRecord(const std::shared_ptr<CItem> &item, const std::string &role) {
    return json{{"role", role},
                {"name", item->getName()},
                {"resourceId", item->getTypeId()},
                {"sourceCode", stored<std::string>(item, "plugin_citySourceItem")},
                {"quantity", stored<int>(item, "plugin_cityQuantity")},
                {"charges", chargesDocument(stored<std::string>(item, "plugin_cityCharges"))},
                {"undroppable", stored<bool>(item, "plugin_cityUndroppable")}};
}
} // namespace
} // namespace seven_suns_merchant_stock_detail

bool CSevenSunsMerchantStock::isSupported() {
    return seven_suns_stock::Items.size() == 97 && seven_suns_stock::Rows.size() == 6;
}

json CSevenSunsMerchantStock::resolveRollsForTests(const std::array<int, 3> &rolls) {
    std::size_t offset = 0;
    return ::seven_suns_merchant_stock_detail::resolve([&] {
        ::seven_suns_merchant_stock_detail::require(offset < rolls.size(), "Missing Seven Suns native roll");
        return rolls[offset++];
    });
}

CSevenSunsMerchantStock::Prepared CSevenSunsMerchantStock::prepare(const std::shared_ptr<CGame> &game,
                                                                   const std::string &lineage, const std::string &area,
                                                                   const std::function<void()> &requireCurrent) {
    ::seven_suns_merchant_stock_detail::require(vstd::event_loop<>::instance()->isMainThread(),
                                                "Seven Suns stock requires its owner thread");
    ::seven_suns_merchant_stock_detail::require(game && requireCurrent && isSupported(),
                                                "Seven Suns stock materialization is unavailable");
    const auto source = ::seven_suns_merchant_stock_detail::sourceActor(lineage, area);
    requireCurrent();
    const auto map = game->getMap();
    const auto context = game->getContext();
    const auto player = map ? map->getAssignedPlayer() : nullptr;
    const auto generation = context->captureTransitionGeneration();
    const auto epoch = game->getMapBindingEpoch();
    ::seven_suns_merchant_stock_detail::require(map && map->getMapName() == "baldursGate" && player,
                                                "Seven Suns stock requires the assigned city player");
    auto lease = map->tryBeginUnsafeOperation();
    ::seven_suns_merchant_stock_detail::require(lease.has_value(), "Seven Suns stock save admission refused");
    const auto check = [&] {
        requireCurrent();
        ::seven_suns_merchant_stock_detail::require(
            context->isActive() && context->isTransitionGenerationCurrent(generation) &&
                game->getContext() == context && game->getMap() == map && game->getMapBindingEpoch() == epoch &&
                map->getGame() == game && map->getAssignedPlayer() == player && lease->isSaveAdmissionHealthy(),
            "Seven Suns stock construction lost its owner");
    };
    try {
        auto barrier = game->getObjectHandler()->beginDefeatConstruction(check);
        check();
        Prepared result;
        result.actor = std::make_shared<CCreature>();
        result.actor->setGame(game);
        game->getSceneManager()->retainStagedObjectLifetime(game, map, result.actor, check);
        check();
        auto actor = result.actor;
        actor->setType("CCreature");
        actor->setTypeId(::seven_suns_merchant_stock_detail::ActorId);
        actor->setName(lineage);
        actor->setLabel("Revealed doppelganger");
        actor->setAnimation("images/monsters/cultist");
        actor->setNpc(false);
        actor->setLevel(1);
        actor->setSw(-20);
        check();
        auto stats = std::make_shared<CStats>();
        stats->setGame(game);
        stats->setType("CStats");
        stats->setStrength(6);
        stats->setAgility(6);
        stats->setIntelligence(6);
        stats->setStamina(4);
        stats->setDmgMin(0);
        stats->setDmgMax(0);
        stats->setHit(75);
        stats->setDamage(0);
        stats->setCrit(0);
        stats->setMainStat("strength");
        actor->setBaseStats(stats);
        auto levelStats = std::make_shared<CStats>();
        levelStats->setGame(game);
        levelStats->setType("CStats");
        actor->setLevelStats(levelStats);
        check();
        ::seven_suns_merchant_stock_detail::put(actor, "affiliation", std::string("cityHostile"), check);
        ::seven_suns_merchant_stock_detail::put(actor, "canStep", true, check);
        ::seven_suns_merchant_stock_detail::put(actor, "sourceCreature", std::string("DOPPSS"), check);
        ::seven_suns_merchant_stock_detail::put(actor, "sourceActor", source, check);
        ::seven_suns_merchant_stock_detail::put(actor, "sourceArea", area, check);
        ::seven_suns_merchant_stock_detail::put(actor, "simulationRegion", area, check);
        ::seven_suns_merchant_stock_detail::put(actor, "sourceAllegiance", 255, check);
        ::seven_suns_merchant_stock_detail::put(actor, "sourceKillXp", 420, check);
        ::seven_suns_merchant_stock_detail::put(actor, "sourceSchedule", -1, check);
        ::seven_suns_merchant_stock_detail::put(actor, "sourceScheduleRaw", std::string("0xffffffff"), check);
        ::seven_suns_merchant_stock_detail::put(actor, "phaseMin", 5, check);
        ::seven_suns_merchant_stock_detail::put(actor, "phaseMax", 7, check);
        ::seven_suns_merchant_stock_detail::put(actor, "plugin_citySevenSunsRevealed", true, check);
        ::seven_suns_merchant_stock_detail::put(actor, "plugin_citySevenSunsLineage", lineage, check);
        auto controller = std::make_shared<CTargetController>();
        controller->setGame(game);
        controller->setType("CTargetController");
        controller->setTarget("player");
        actor->setController(controller);
        result.controller = controller;
        auto fight = std::make_shared<CMonsterFightController>();
        fight->setGame(game);
        fight->setType("CMonsterFightController");
        actor->setFightController(fight);
        result.fightController = fight;
        check();
        auto attack = game->createObject<CInteraction>("Attack");
        check();
        ::seven_suns_merchant_stock_detail::require(
            attack && attack->getGame() == game && attack->getTypeId() == "Attack", "Missing native Attack action");
        actor->addAction(attack);
        result.attack = attack;
        check();
        auto weapon = std::make_shared<CWeapon>();
        ::seven_suns_merchant_stock_detail::itemProperties(
            weapon, game, lineage, "weapon", "S1-12", ::seven_suns_merchant_stock_detail::WeaponId, 1, {}, 96, 0, 0, 0,
            1, 1, ::seven_suns_merchant_stock_detail::WeaponSha, "Doppelganger natural attack",
            "images/items/weapons/sword", true, check);
        auto bonus = std::make_shared<CStats>();
        bonus->setGame(game);
        bonus->setType("CStats");
        bonus->setDmgMin(1);
        bonus->setDmgMax(12);
        bonus->setHit(0);
        weapon->setBonus(bonus);
        actor->addItem(weapon);
        check();
        actor->equipItem("0", weapon);
        check();
        result.owned.push_back(weapon);
        const auto selection = ::seven_suns_merchant_stock_detail::resolve([&] {
            check();
            const int value = vstd::rand(1, 20);
            check();
            return value;
        });
        const auto &selected = selection.at("outcome");
        if (selected.at("kind").get<std::string>() == "item") {
            const auto &definition =
                ::seven_suns_merchant_stock_detail::itemDefinition(selected.at("code").get<std::string>());
            auto treasure = std::make_shared<CItem>();
            ::seven_suns_merchant_stock_detail::itemProperties(
                treasure, game, lineage, "treasure", std::string(definition.code), std::string(definition.resourceId),
                selected.at("quantity").get<int>(), definition.charges, definition.flags, definition.itemType,
                definition.price, definition.lore, definition.stackSize, definition.enchantment,
                std::string(definition.fingerprint), std::string(definition.label), std::string(definition.animation),
                false, check);
            actor->addItem(treasure);
            check();
            result.owned.push_back(treasure);
        }
        actor->setGold(selected.at("gold").get<int>());
        actor->setHp(28);
        actor->setMana(0);
        check();
        json owned = json::array();
        for (std::size_t index = 0; index < result.owned.size(); ++index)
            owned[owned.size()] = ::seven_suns_merchant_stock_detail::ownedRecord(result.owned[index],
                                                                                  index == 0 ? "weapon" : "treasure");
        result.receipt = ::seven_suns_merchant_stock_detail::certificate(lineage, area, selection);
        ::seven_suns_merchant_stock_detail::require(owned.dump() == result.receipt.at("owned").dump(),
                                                    "Seven Suns initial owned stock differs from source");
        ::seven_suns_merchant_stock_detail::require(::seven_suns_merchant_stock_detail::encode(result.receipt).size() <=
                                                        8192,
                                                    "Seven Suns materialization receipt exceeds bound");
        ::seven_suns_merchant_stock_detail::put(actor, ::seven_suns_merchant_stock_detail::StockKey,
                                                ::seven_suns_merchant_stock_detail::encode(result.receipt), check);
        ::seven_suns_merchant_stock_detail::put(actor, "plugin_cityInventoryInitialized", true, check);
        ::seven_suns_merchant_stock_detail::put(actor, "plugin_cityHooksInstalled", true, check);
        validatePrepared(result, game, lineage, area, check);
        check();
        lease->finish();
        return result;
    } catch (...) {
        lease->quarantine();
        throw;
    }
}

void CSevenSunsMerchantStock::validateSettled(const std::shared_ptr<CCreature> &actor, const json &receipt,
                                              const std::shared_ptr<CGame> &game, const std::string &lineage,
                                              const std::string &area, const std::function<void()> &requireCurrent) {
    requireCurrent();
    const auto source = ::seven_suns_merchant_stock_detail::sourceActor(lineage, area);
    ::seven_suns_merchant_stock_detail::validateCertificate(receipt, lineage, area);
    ::seven_suns_merchant_stock_detail::require(
        actor && typeid(*actor) == typeid(CCreature) && actor->getGame() == game &&
            actor->getTypeId() == ::seven_suns_merchant_stock_detail::ActorId && actor->getName() == lineage &&
            actor->getType() == "CCreature" &&
            ::seven_suns_merchant_stock_detail::stored<std::string>(actor, "sourceCreature") == "DOPPSS" &&
            ::seven_suns_merchant_stock_detail::stored<std::string>(actor, "sourceActor") == source &&
            ::seven_suns_merchant_stock_detail::stored<std::string>(actor, "sourceArea") == area &&
            ::seven_suns_merchant_stock_detail::stored<std::string>(actor, "simulationRegion") == area &&
            ::seven_suns_merchant_stock_detail::stored<bool>(actor, "plugin_citySevenSunsRevealed") &&
            ::seven_suns_merchant_stock_detail::stored<std::string>(actor, "plugin_citySevenSunsLineage") == lineage &&
            ::seven_suns_merchant_stock_detail::stored<bool>(actor, "plugin_cityInventoryInitialized") &&
            ::seven_suns_merchant_stock_detail::stored<bool>(actor, "plugin_cityHooksInstalled") &&
            ::seven_suns_merchant_stock_detail::stored<int>(actor, "sourceKillXp") == 420 &&
            ::seven_suns_merchant_stock_detail::stored<int>(actor, "sourceSchedule") == -1 &&
            ::seven_suns_merchant_stock_detail::stored<std::string>(actor, "sourceScheduleRaw") == "0xffffffff" &&
            ::seven_suns_merchant_stock_detail::stored<int>(actor, "sourceAllegiance") == 255 &&
            ::seven_suns_merchant_stock_detail::stored<int>(actor, "phaseMin") == 5 &&
            ::seven_suns_merchant_stock_detail::stored<int>(actor, "phaseMax") == 7 &&
            ::seven_suns_merchant_stock_detail::stored<std::string>(actor,
                                                                    ::seven_suns_merchant_stock_detail::StockKey) ==
                ::seven_suns_merchant_stock_detail::encode(receipt),
        "Seven Suns settled materialization identity changed");
    requireCurrent();
}

void CSevenSunsMerchantStock::validatePrepared(const Prepared &prepared, const std::shared_ptr<CGame> &game,
                                               const std::string &lineage, const std::string &area,
                                               const std::function<void()> &requireCurrent) {
    validateSettled(prepared.actor, prepared.receipt, game, lineage, area, requireCurrent);
    auto actor = prepared.actor;
    auto stats = actor->getStats();
    requireCurrent();
    ::seven_suns_merchant_stock_detail::require(
        prepared.controller && typeid(*prepared.controller) == typeid(CTargetController) &&
            prepared.controller->getGame() == game && prepared.controller->getTarget() == "player" &&
            actor->getController() == prepared.controller && prepared.fightController &&
            typeid(*prepared.fightController) == typeid(CMonsterFightController) &&
            prepared.fightController->getGame() == game && actor->getFightController() == prepared.fightController &&
            prepared.attack && prepared.attack->getGame() == game && prepared.attack->getTypeId() == "Attack" &&
            actor->getActions() == std::set<std::shared_ptr<CInteraction>>{prepared.attack},
        "Seven Suns prepared native controller or Attack action changed");
    requireCurrent();
    ::seven_suns_merchant_stock_detail::require(
        actor->isAlive() && actor->getHp() == 28 && actor->getHpMax() == 28 && actor->getMana() == 0 &&
            !actor->isNpc() && actor->getStringProperty("affiliation") == "cityHostile" && !actor->getRace() &&
            !actor->getCreatureClass() && actor->getClassTracks().empty() && actor->getTemplates().empty() &&
            actor->getEffects().empty() && stats->getDmgMin() == 1 && stats->getDmgMax() == 12 &&
            stats->getHit() == 75 && stats->getDamage() == 0 && stats->getCrit() == 0 && stats->getStrength() == 6 &&
            stats->getAgility() == 6 && stats->getIntelligence() == 6 && stats->getStamina() == 4 &&
            (prepared.owned.size() == 1 || prepared.owned.size() == 2),
        "Seven Suns prepared native profile changed");
    const auto equipment = actor->getEquipped();
    ::seven_suns_merchant_stock_detail::require(prepared.owned[0] && equipment.size() == 1 && equipment.contains("0") &&
                                                    equipment.at("0") == prepared.owned[0] &&
                                                    typeid(*prepared.owned[0]) == typeid(CWeapon),
                                                "Seven Suns source weapon ownership changed");
    std::set<std::shared_ptr<CItem>> expected(prepared.owned.begin(), prepared.owned.end());
    ::seven_suns_merchant_stock_detail::require(actor->getAllItems() == expected &&
                                                    expected.size() == prepared.owned.size(),
                                                "Seven Suns prepared stock has missing or duplicate ownership");
    for (std::size_t index = 0; index < prepared.owned.size(); ++index) {
        requireCurrent();
        const auto &item = prepared.owned[index];
        ::seven_suns_merchant_stock_detail::require(
            item && item->getGame() == game &&
                ::seven_suns_merchant_stock_detail::ownedRecord(item, index == 0 ? "weapon" : "treasure").dump() ==
                    prepared.receipt.at("owned").at(index).dump(),
            "Seven Suns prepared stock metadata changed");
        const bool weapon = index == 0;
        const auto &definition = weapon ? seven_suns_stock::Items.front()
                                        : ::seven_suns_merchant_stock_detail::itemDefinition(
                                              prepared.receipt.at("outcome").at("code").get<std::string>());
        const auto flags = weapon ? 96 : definition.flags;
        ::seven_suns_merchant_stock_detail::require(
            (weapon ? typeid(*item) == typeid(CWeapon) : typeid(*item) == typeid(CItem)) &&
                item->getType() == (weapon ? "CWeapon" : "CItem") &&
                ::seven_suns_merchant_stock_detail::stored<std::string>(item, "plugin_citySourceItemFingerprint") ==
                    (weapon ? ::seven_suns_merchant_stock_detail::WeaponSha : std::string(definition.fingerprint)) &&
                ::seven_suns_merchant_stock_detail::stored<int>(item, "plugin_citySourceItemFlags") == flags &&
                ::seven_suns_merchant_stock_detail::stored<int>(item, "plugin_citySourceEnchantment") ==
                    (weapon ? 1 : definition.enchantment) &&
                ::seven_suns_merchant_stock_detail::stored<int>(item, "plugin_citySourceFlags") == 0 &&
                ::seven_suns_merchant_stock_detail::stored<int>(item, "plugin_cityItemType") ==
                    (weapon ? 0 : definition.itemType) &&
                ::seven_suns_merchant_stock_detail::stored<int>(item, "plugin_cityValue") ==
                    (weapon ? 0 : definition.price) &&
                ::seven_suns_merchant_stock_detail::stored<int>(item, "plugin_cityLore") ==
                    (weapon ? 0 : definition.lore) &&
                ::seven_suns_merchant_stock_detail::stored<int>(item, "plugin_cityStackSize") ==
                    (weapon ? 1 : definition.stackSize) &&
                ::seven_suns_merchant_stock_detail::stored<bool>(item, "plugin_cityUnstealable") == weapon &&
                ::seven_suns_merchant_stock_detail::stored<bool>(item, "plugin_cityTradeable") ==
                    (!weapon && bool(flags & 4)) &&
                ::seven_suns_merchant_stock_detail::stored<bool>(item, "plugin_cityUnidentified") == !weapon &&
                ::seven_suns_merchant_stock_detail::stored<bool>(item, "plugin_cityAbilitiesPending") == !weapon &&
                ::seven_suns_merchant_stock_detail::stored<std::string>(item, "plugin_cityStockLineage") == lineage &&
                ::seven_suns_merchant_stock_detail::stored<std::string>(item, "plugin_cityStockKind") ==
                    (weapon ? "weapon" : "treasure"),
            "Seven Suns prepared source metadata changed");
        requireCurrent();
    }
    ::seven_suns_merchant_stock_detail::require(
        actor->getGold() == prepared.receipt.at("outcome").at("gold").get<int>(), "Seven Suns prepared gold changed");
    requireCurrent();
}
