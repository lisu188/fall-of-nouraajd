// Copyright (C) 2026 Andrzej Lis
// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "seven_suns_warning_fixture.h"
#include "handler/CSevenSunsMerchantDialogue.h"
#include "core/CSlotConfig.h"
#include "object/CInteraction.h"

struct SevenSunsMerchantFixture : SevenSunsWarningFixture {
    static constexpr const char *MerchantStateKey = "plugin_citySevenSunsMerchantState";
    static constexpr std::array<const char *, 4> Names{"cityAr0601Actor1", "cityAr0601Actor3", "cityAr0602Actor1",
                                                       "cityAr0602Actor2"};
    static constexpr std::array<const char *, 4> Sources{"AR0601#actor1", "AR0601#actor3", "AR0602#actor1",
                                                         "AR0602#actor2"};
    std::array<std::shared_ptr<CItem>, 4> oldItems;
    std::array<std::shared_ptr<CEffect>, 4> oldEffects;
    int merchantDestroyed = 0, newDestroyed = 0;
    std::function<void()> duringActionFactory;
    SevenSunsMerchantFixture() {
        clock->setStringProperty("sevenSunsMerchantDefinition",
                                 "city-json:{\"version\":1,\"dialogue\":\"DOPMER\","
                                 "\"fingerprint\":\"e0410b2b978573d0e921a63bf3a55fd53d49c291f556b6e0a045db63762030a7\","
                                 "\"stockContract\":\"doppss-native-v1\"}");
        auto objects = game->getObjectHandler();
        auto slots = std::make_shared<CSlotConfig>();
        auto rightHand = std::make_shared<CSlot>();
        rightHand->setSlotName("RightHand");
        rightHand->setTypes({"CWeapon"});
        slots->setConfiguration({{"0", rightHand}});
        objects->registerType("UnitMerchantRightHandSlots", [slots] { return slots; });
        objects->registerConfig("slotConfiguration",
                                std::make_shared<json>(json{{"class", "UnitMerchantRightHandSlots"}}));
        objects->registerType("CCreature", [this] {
            ++actorFactories;
            return std::make_shared<CCreature>();
        });
        objects->registerType("CWeapon", [this] {
            ++itemFactories;
            return std::make_shared<CWeapon>();
        });
        objects->registerType("CStats", [] { return std::make_shared<CStats>(); });
        objects->registerType("CTargetController", [] { return std::make_shared<CTargetController>(); });
        objects->registerType("CInteraction", [this] {
            if (duringActionFactory)
                duringActionFactory();
            return std::make_shared<CInteraction>();
        });
        objects->registerType("CMonsterFightController", [] { return std::make_shared<CMonsterFightController>(); });
        objects->registerConfig(
            "Attack", std::make_shared<json>(json{{"class", "CInteraction"}, {"properties", json::object()}}));
        objects->registerConfig(
            "citySevenSunsRevealedDoppss",
            std::make_shared<json>(
                json{{"class", "CCreature"},
                     {"properties",
                      {{"npc", false},
                       {"affiliation", "cityHostile"},
                       {"level", 1},
                       {"baseStats",
                        {{"class", "CStats"},
                         {"properties",
                          {{"strength", 6},
                           {"agility", 6},
                           {"intelligence", 6},
                           {"stamina", 4},
                           {"mainStat", "strength"},
                           {"dmgMin", 0},
                           {"dmgMax", 0},
                           {"hit", 75}}}}},
                       {"levelStats", {{"class", "CStats"}, {"properties", json::object()}}},
                       {"fightController", {{"class", "CMonsterFightController"}, {"properties", json::object()}}},
                       {"controller", {{"class", "CTargetController"}, {"properties", {{"target", "player"}}}}},
                       {"actions", json::array({json{{"ref", "Attack"}}})},
                       {"sourceCreature", "DOPPSS"},
                       {"sourceKillXp", 420},
                       {"sourceAllegiance", 255},
                       {"plugin_citySevenSunsRevealed", true}}}}));
        objects->registerConfig(
            "citySevenSunsDoppssWeapon",
            std::make_shared<json>(json{
                {"class", "CWeapon"},
                {"properties",
                 {{"plugin_citySourceItem", "S1-12"},
                  {"plugin_cityUndroppable", true},
                  {"tradeable", false},
                  {"bonus", {{"class", "CStats"}, {"properties", {{"dmgMin", 1}, {"dmgMax", 12}, {"hit", 0}}}}}}}}));
        for (std::size_t i = 0; i < 4; ++i) {
            auto actor = protectedActors[i];
            const std::string area = i < 2 ? "AR0601" : "AR0602";
            actor->setNpc(true);
            actor->setAffiliation("cityResidents");
            actor->setStringProperty("sourceActor", Sources[i]);
            actor->setStringProperty("sourceArea", area);
            actor->setStringProperty("simulationRegion", area);
            actor->setStringProperty("sourceCreature", "DOPMER");
            actor->setStringProperty("sourceDialogue", "DOPMER");
            actor->setStringProperty("label", "Merchant");
            actor->setNumericProperty("sourceAllegiance", 128);
            actor->setBoolProperty("plugin_cityHooksInstalled", true);
            auto item = std::make_shared<CItem>();
            item->setGame(game);
            item->setName("oldMerchantStock" + std::to_string(i));
            actor->addItem(item);
            oldItems[i] = item;
            auto effect = std::make_shared<CEffect>();
            effect->setGame(game);
            effect->setCaster(actor);
            effect->setVictim(actor);
            effect->setDuration(10);
            effect->setTimeLeft(10);
            actor->addEffect(effect);
            oldEffects[i] = effect;
            auto death = std::make_shared<CCustomTrigger>(Names[i], "onDestroy", [this, i](auto object, auto) {
                if (object == protectedActors[i])
                    ++merchantDestroyed;
                else
                    ++newDestroyed;
            });
            death->setName("merchantNativeDeathObserver" + std::to_string(i));
            map->getEventHandler()->registerTrigger(death);
        }
        focus(0);
    }
    void focus(std::size_t i) {
        map->setActiveSimulationRegion(i < 2 ? "AR0601" : "AR0602");
        auto p = protectedActors[i]->getCoords();
        player->relocateWithoutMoveHooks(Coords(p.x - 1, p.y, p.z));
    }
    std::unique_ptr<CSevenSunsMerchantDialogue> beginMerchant(std::size_t i = 0, std::function<void()> guard = {}) {
        return CSevenSunsMerchantDialogue::begin(game, clock, protectedActors[i], std::move(guard));
    }
    static json step(CSevenSunsMerchantDialogue &session, int edge) {
        return session.advance(session.view().at("revision").get<int>(), edge);
    }
    static json finish(CSevenSunsMerchantDialogue &session, const std::vector<int> &path) {
        json view = session.view();
        for (int edge : path)
            view = step(session, edge);
        return view;
    }
    void earlierConversations(int count) {
        if (count > 0) {
            auto first = beginMerchant();
            finish(*first, {0, 3});
        }
        if (count > 1) {
            auto second = beginMerchant();
            finish(*second, {13, 16});
        }
    }
    json merchantDocument() const {
        auto text = map->getStringProperty(MerchantStateKey);
        return text.empty() ? json{{"version", 1}, {"actors", json::object()}}
                            : json::parse(std::string_view(text).substr(std::string_view("city-json:").size()));
    }
    json merchantRow(std::size_t i = 0) const { return merchantDocument().at("actors").at(Names[i]); }
    json settle() { return CSevenSunsMerchantDialogue::settle(game, clock, {}); }
    std::shared_ptr<CCreature> replacement(std::size_t i = 0) const {
        return std::dynamic_pointer_cast<CCreature>(
            clock->getObjectProperty(std::string("plugin_citySevenSunsMerchantNew_") + Names[i]));
    }
    bool oldOwnershipIntact(std::size_t i = 0) const {
        auto actor = protectedActors[i];
        return actor->isAlive() && actor->getItems().contains(oldItems[i]) &&
               actor->getEffects().contains(oldEffects[i]) && oldEffects[i]->getCaster() == actor &&
               oldEffects[i]->getVictim() == actor;
    }
};
