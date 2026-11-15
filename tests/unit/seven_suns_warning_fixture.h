// Copyright (C) 2026 Andrzej Lis
// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include "core/CController.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CMap.h"
#include "core/CSerialization.h"
#include "core/CStats.h"
#include "handler/CEventHandler.h"
#include "handler/CObjectHandler.h"
#include "handler/CSevenSunsDialogue.h"
#include "object/CBuilding.h"
#include "object/CCreature.h"
#include "object/CEffect.h"
#include "object/CItem.h"
#include "object/CPlayer.h"
#include "object/CQuest.h"
#include "object/CTrigger.h"
#include "veventloop.h"

#include <array>
#include <functional>
#include <initializer_list>
#include <memory>
#include <set>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <utility>

// Synthetic native lifecycle fixture. Source dialogue/stock/original-engine fidelity is separate.
struct SevenSunsWarningFixture {
    static constexpr const char *StateKey = "plugin_citySevenSunsWarningState";
    static constexpr const char *ActorKey = "plugin_citySevenSunsWarningActor";
    static constexpr const char *QuestId = "citySevenSunsWarningLead";
    std::shared_ptr<CGame> game = std::make_shared<CGame>();
    std::shared_ptr<CMap> map = std::make_shared<CMap>();
    std::shared_ptr<CPlayer> player = std::make_shared<CPlayer>();
    std::shared_ptr<CGameObject> clock = std::make_shared<CBuilding>();
    std::shared_ptr<CCreature> warning = std::make_shared<CCreature>();
    std::array<std::shared_ptr<CCreature>, 6> protectedActors;
    std::shared_ptr<CItem> bagItem = std::make_shared<CItem>();
    std::shared_ptr<CItem> equippedItem = std::make_shared<CWeapon>();
    std::shared_ptr<CEffect> effect = std::make_shared<CEffect>();
    int actorFactories = 0;
    int itemFactories = 0;
    int questFactories = 0;
    int destroyCalls = 0;
    std::function<void()> duringJournalFactory;

    static void initialize(const std::shared_ptr<CCreature> &actor) {
        auto stats = std::make_shared<CStats>();
        stats->setMainStat("stamina");
        stats->setStamina(10);
        actor->setBaseStats(stats);
        actor->setLevelStats(std::make_shared<CStats>());
        actor->setLevel(1);
        actor->setHp(10);
        actor->setController(std::make_shared<CController>());
        actor->setFightController(std::make_shared<CMonsterFightController>());
    }

    SevenSunsWarningFixture() {
        vstd::event_loop<>::instance()->resetQuit();
        map->setGame(game);
        map->setMapName("baldursGate");
        game->setMap(map);
        auto objects = game->getObjectHandler();
        objects->registerType("CPlayerController", [] { return std::make_shared<CPlayerController>(); });
        objects->registerType("CPlayerFightController", [] { return std::make_shared<CPlayerFightController>(); });
        player->setGame(game);
        initialize(player);
        player->setPosX(0);
        player->setPosY(0);
        map->setPlayer(player);
        map->setNumericProperty("plugin_cityPhase", 5);
        map->setStringProperty("activeSimulationRegion", "AR0601");
        map->setStringProperty("plugin_cityHistory", "city-json:{}");
        map->setStringProperty("plugin_cityTalked", "city-json:{}");
        clock->setGame(game);
        clock->setName("cityClock");
        map->addObject(std::dynamic_pointer_cast<CMapObject>(clock));
        clock->setStringProperty("sevenSunsWarningDefinition",
                                 "city-json:{\"version\":1,\"dialogue\":\"DOPPSM\","
                                 "\"fingerprint\":\"263ba285fac3cc7d486ce0c4223ce4af574b257b7ce224d8755b988906df6aac\","
                                 "\"journalQuest\":\"citySevenSunsWarningLead\"}");
        warning->setGame(game);
        warning->setName("cityAr0601Actor2");
        initialize(warning);
        warning->setPosX(1);
        warning->setPosY(0);
        warning->setNpc(true);
        warning->setAffiliation("cityResidents");
        warning->setCanStep(false);
        warning->setStringProperty("sourceCreature", "DOPPSM");
        warning->setStringProperty("sourceDialogue", "DOPPSM");
        warning->setStringProperty("sourceArea", "AR0601");
        warning->setStringProperty("sourceActor", "AR0601#actor2");
        warning->setStringProperty("simulationRegion", "AR0601");
        warning->setStringProperty("label", "Merchant");
        for (const auto &item : {bagItem, equippedItem}) {
            item->setGame(game);
            item->setBonus(std::make_shared<CStats>());
        }
        bagItem->setName("unitWarningOwnedBagItem");
        equippedItem->setName("unitWarningOwnedEquipment");
        warning->addItem(bagItem);
        warning->setEquipped({{"0", equippedItem}});
        effect->setGame(game);
        effect->setName("unitWarningRetainedEffect");
        effect->setDuration(10);
        effect->setTimeLeft(10);
        effect->setCaster(warning);
        effect->setVictim(warning);
        warning->addEffect(effect);
        map->addObject(warning);
        auto observer =
            std::make_shared<CCustomTrigger>(warning->getName(), "onDestroy", [this](auto, auto) { ++destroyCalls; });
        observer->setName("unitWarningDestroyObserver");
        map->getEventHandler()->registerTrigger(observer);
        constexpr std::array<const char *, 6> names{"cityAr0601Actor1", "cityAr0601Actor3", "cityAr0602Actor1",
                                                    "cityAr0602Actor2", "cityAr0603Actor1", "cityAr0603Actor2"};
        for (std::size_t index = 0; index < protectedActors.size(); ++index) {
            auto actor = std::make_shared<CCreature>();
            actor->setGame(game);
            actor->setName(names[index]);
            initialize(actor);
            actor->setPosX(static_cast<int>(index) + 3);
            map->addObject(actor);
            protectedActors[index] = actor;
        }
        objects->registerType("CCreature", [this] {
            ++actorFactories;
            return std::make_shared<CCreature>();
        });
        objects->registerType("CItem", [this] {
            ++itemFactories;
            return std::make_shared<CItem>();
        });
        objects->registerType("CQuest", [this] {
            ++questFactories;
            if (duringJournalFactory)
                duringJournalFactory();
            return std::make_shared<CQuest>();
        });
        objects->registerConfig(
            QuestId, std::make_shared<json>(
                         json{{"class", "CQuest"},
                              {"properties",
                               {{"description", "Seven Suns warning"},
                                {"objective", "A merchant warned that the Seven Suns is unsafe and left the building."},
                                {"reward", "This lead grants no gold, experience, or items."},
                                {"hint", "Keep this warning when speaking to Scar; the infestation and Jhasso remain "
                                         "separate matters."}}}}));
    }

    std::unique_ptr<CSevenSunsDialogue> begin(std::function<void()> check = {}) {
        return CSevenSunsDialogue::begin(game, clock, warning, std::move(check));
    }

    json state() const {
        auto encoded = map->getStringProperty(StateKey);
        if (encoded.empty())
            return nullptr;
        constexpr std::string_view prefix = "city-json:";
        return json::parse(encoded.starts_with(prefix) ? std::string_view(encoded).substr(prefix.size())
                                                       : std::string_view(encoded));
    }

    static json step(CSevenSunsDialogue &session, int edge) {
        return session.advance(session.view().at("revision").get<int>(), edge);
    }

    static json finish(CSevenSunsDialogue &session, std::initializer_list<int> edges = {0, 7, 9}) {
        json result = session.view();
        for (const int edge : edges)
            result = step(session, edge);
        return result;
    }

    std::shared_ptr<CQuest> journal() const {
        for (const auto &quest : player->getQuests())
            if (quest && quest->getTypeId() == QuestId)
                return quest;
        return nullptr;
    }

    bool stockAndEffectIntact() const {
        return warning->isAlive() && warning->getHp() == 10 && warning->getItems().size() == 1 &&
               warning->getItems().contains(bagItem) && warning->getEquipped().size() == 1 &&
               warning->getEquipped().at("0") == equippedItem && warning->getEffects().size() == 1 &&
               warning->getEffects().contains(effect) && effect->getCaster() == warning &&
               effect->getVictim() == warning && warning->getCoords() == Coords(1, 0, 0);
    }

    bool protectedActorsIntact() const {
        for (const auto &actor : protectedActors)
            if (map->getObjectByName(actor->getName()) != actor || !actor->isAlive() || actor->getHp() != 10)
                return false;
        return true;
    }
};
