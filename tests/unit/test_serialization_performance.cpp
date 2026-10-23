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
#include "core/CGameContext.h"
#include "core/CMap.h"
#include "core/CProvider.h"
#include "core/CSaveFormat.h"
#include "core/CSerialization.h"
#include "core/CController.h"
#include "core/CLoader.h"
#include "core/CTypes.h"
#include "object/CCreature.h"
#include "object/CEffect.h"
#include "object/CTile.h"
#include "object/CMapObject.h"
#include "object/CPlayer.h"
#include "object/CQuest.h"
#include "handler/CFightHandler.h"
#include "handler/CEventHandler.h"
#include "object/CTrigger.h"
#include "test_harness.h"
#include "veventloop.h"

#include <algorithm>
#include <chrono>
#include <cstddef>
#include <iostream>
#include <memory>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {

constexpr int MAP_LOAD_OBJECT_COUNT = 32;
constexpr int MAP_LOAD_PROPERTY_COUNT = 8;
constexpr int EFFECT_GRAPH_ACTOR_COUNT = 8;
constexpr std::size_t EFFECT_GRAPH_BYTES_PER_ACTOR = 8192;

class ScalarMetadataTile : public CTile {
  public:
    mutable std::size_t metadataCalls = 0;

    std::shared_ptr<vstd::meta> meta() override {
        ++metadataCalls;
        return CTile::meta();
    }
    std::shared_ptr<const vstd::meta> meta() const override {
        ++metadataCalls;
        return CTile::meta();
    }
};

class SaveAdmissionBudgetMap : public CMap {
  public:
    std::shared_ptr<vstd::meta> meta() override {
        if (observeGraph) {
            ++graphVisits;
            throw std::runtime_error("intentional save admission graph stop before resource writes");
        }
        return CMap::meta();
    }
    std::shared_ptr<const vstd::meta> meta() const override {
        if (observeGraph) {
            ++graphVisits;
            throw std::runtime_error("intentional save admission graph stop before resource writes");
        }
        return CMap::meta();
    }
    bool observeGraph = false;
    mutable std::size_t graphVisits = 0;
};

class SaveAdmissionBudgetQuest : public CQuest {
  public:
    void captureJournal(bool) override { ++captures; }
    std::size_t captures = 0;
};

void testRejectedSaveAdmissionHasZeroSnapshotWork() {
    constexpr int ATTEMPTS = 256;
    CTypes::register_type<CMap, CGameObject>();
    auto game = std::make_shared<CGame>();
    game->getObjectHandler()->registerType("CPlayerController", [] { return std::make_shared<CPlayerController>(); });
    game->getObjectHandler()->registerType("CPlayerFightController",
                                           [] { return std::make_shared<CPlayerFightController>(); });
    auto map = std::make_shared<SaveAdmissionBudgetMap>();
    map->setGame(game);
    map->setMapName("empty");
    game->setMap(map);
    auto player = std::make_shared<CPlayer>();
    player->setGame(game);
    player->setName("player");
    player->setController(std::make_shared<CPlayerController>());
    player->setFightController(std::make_shared<CPlayerFightController>());
    auto quest = std::make_shared<SaveAdmissionBudgetQuest>();
    quest->setGame(game);
    player->setQuests({quest});
    map->setObjects({player});
    expect_true(map->getPlayer() == player, "the rejection budget must include an actual journal owner");
    const auto resources = game->getResourcesProvider();
    const auto slot =
        "performance-save-admission-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count());
    auto operation = map->tryBeginUnsafeOperation();
    expect_true(operation.has_value(), "the zero-work budget must hold real unsafe admission");
    if (!operation) {
        game->getContext()->shutdown();
        return;
    }
    map->observeGraph = true;
    int rejected = 0;
    for (int index = 0; index < ATTEMPTS; ++index) {
        rejected += !CMapLoader::saveWithResult(map, slot);
    }
    const auto captures = quest->captures;
    const auto graphVisits = map->graphVisits;
    const int providerOutputs = !resources->getPath(CSaveFormat::primaryPath(slot)).empty() +
                                !resources->getPath(CSaveFormat::backupPath(slot)).empty();
    expect_true(rejected == ATTEMPTS && captures == 0 && graphVisits == 0 && providerOutputs == 0,
                "each rejected save must have zero journal/graph work and create no primary or backup output");
    operation->finish();
    expect_true(!CMapLoader::saveWithResult(map, slot) && quest->captures == 1 && map->graphVisits == 1,
                "the released positive control must reach journal capture and the intentional graph stop once");
    map->observeGraph = false;
    std::cout << "[performance] rejected save admission: attempts=" << ATTEMPTS << " rejected=" << rejected
              << " journal=" << captures << " graph=" << graphVisits << " providerOutputs=" << providerOutputs
              << " workBudget=0 controlJournal=" << quest->captures << " controlGraph=" << map->graphVisits << '\n';
    game->getContext()->shutdown();
}
class RejectedEncounterController : public CFightController {
  public:
    int starts = 0;
    int actions = 0;
    int ends = 0;
    void start(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override { ++starts; }
    bool control(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override {
        ++actions;
        return true;
    }
    bool isCancelled(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override { return true; }
    void end(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override { ++ends; }
};

void testSnapshotAdmissionRejectsEncountersBeforeMutation() {
    constexpr int ATTEMPTS = 64;
    auto game = std::make_shared<CGame>();
    auto map = std::make_shared<CMap>();
    map->setGame(game);
    game->setMap(map);
    map->setBoolProperty("guardNativeEncounterSaves", true);
    auto attacker = std::make_shared<CCreature>();
    auto enemy = std::make_shared<CCreature>();
    auto attackerController = std::make_shared<RejectedEncounterController>();
    auto enemyController = std::make_shared<RejectedEncounterController>();
    for (const auto &actor : {attacker, enemy}) {
        actor->setGame(game);
        actor->setBaseStats(std::make_shared<CStats>());
        actor->setLevelStats(std::make_shared<CStats>());
        actor->getBaseStats()->setMainStat("strength");
        actor->getBaseStats()->setStamina(10);
        actor->getBaseStats()->setAgility(10);
        actor->setLevel(1);
        actor->setHp(10);
    }
    attacker->setName("rejectedEncounterAttacker");
    enemy->setName("rejectedEncounterEnemy");
    attacker->setAffiliation("admissionSideA");
    enemy->setAffiliation("admissionSideB");
    attacker->setFightController(attackerController);
    enemy->setFightController(enemyController);
    map->setObjects({attacker, enemy});
    map->setStringProperty("combatHistory", "bounded admission sentinel");
    auto snapshot = map->tryBeginSaveSnapshot();
    expect_true(snapshot.has_value(), "the rejection work budget must own real snapshot admission");
    int rejected = 0;
    for (int index = 0; index < ATTEMPTS; ++index) {
        rejected += CFightHandler::fightManyResult(attacker, {enemy}).outcome == CFightOutcome::Invalid;
    }
    const int starts = attackerController->starts + enemyController->starts;
    const int actions = attackerController->actions + enemyController->actions;
    const int ends = attackerController->ends + enemyController->ends;
    expect_true(rejected == ATTEMPTS && starts == 0 && actions == 0 && ends == 0 &&
                    map->getStringProperty("combatHistory") == "bounded admission sentinel",
                "rejected encounters must perform zero controller callbacks and no combat-history writes");
    std::cout << "[performance] snapshot-rejected encounters: attempts=" << ATTEMPTS << " rejected=" << rejected
              << " starts=" << starts << " actions=" << actions << " ends=" << ends << " callbackBudget=0\n";
    snapshot.reset();
    game->getContext()->shutdown();
}
void testScalarPropertyMetadataWorkIsBounded() {
    constexpr std::size_t tileCount = 32;
    constexpr std::size_t propertyCount = 5;
    std::size_t directCalls = 0;
    std::size_t decodedCalls = 0;
    CSerializationReadContext context(true, "performance.scalarMetadata");
    for (std::size_t index = 0; index < tileCount; ++index) {
        auto direct = std::make_shared<ScalarMetadataTile>();
        auto decoded = std::make_shared<ScalarMetadataTile>();
        direct->metadataCalls = decoded->metadataCalls = 0;
        direct->setStringProperty("animation", "images/tiles/ground");
        direct->setStringProperty("label", "Ground");
        direct->setStringProperty("tileType", "ground");
        direct->setBoolProperty("canStep", true);
        direct->setNumericProperty("movementCost", 2);
        CSerialization::setProperty(decoded, "animation", json("images/tiles/ground"), context);
        CSerialization::setProperty(decoded, "label", json("Ground"), context);
        CSerialization::setProperty(decoded, "tileType", json("ground"), context);
        CSerialization::setProperty(decoded, "canStep", json(true), context);
        CSerialization::setProperty(decoded, "movementCost", json(2), context);
        directCalls += direct->metadataCalls;
        decodedCalls += decoded->metadataCalls;
        expect_true(decoded->getAnimation() == direct->getAnimation() &&
                        decoded->getStringProperty("label") == direct->getStringProperty("label") &&
                        decoded->getTileType() == direct->getTileType() && decoded->canStep() == direct->canStep() &&
                        decoded->getMovementCost() == direct->getMovementCost(),
                    "bounded scalar metadata work must preserve the initialized tile properties");
    }
    // Each public decode scopes the property's type name and resolves its scalar type once.
    const auto budget = directCalls + 2 * tileCount * propertyCount;
    std::cout << "[performance] scalar metadata calls=" << decodedCalls << " direct=" << directCalls
              << " budget=" << budget << '\n';
    expect_true(decodedCalls <= budget, "scalar decoding must not repeat the reflected property type lookup");
}

void testTypedCodecWorkIsBoundedPerOperation() {
    struct Value {
        int number;
    };
    struct Work {
        std::size_t encodes = 0;
        std::size_t decodes = 0;
    };
    constexpr int operation_count = 512;
    auto work = std::make_shared<Work>();
    CTypes::registerJsonCodec<Value>(
        [work](const Value &value) -> CSerializationResult<json> {
            ++work->encodes;
            return json(value.number);
        },
        [work](const std::shared_ptr<CGame> &, const json &document) -> CSerializationResult<Value> {
            ++work->decodes;
            return Value{document.get<int>()};
        });
    const auto registered = CTypes::codecCount();
    for (int index = 0; index < operation_count; ++index) {
        auto encoded = CSerialization::serializeExpected(Value{index});
        expect_true(encoded.has_value(), "bounded typed codec workload must serialize");
        if (!encoded) {
            continue;
        }
        auto decoded = CSerialization::deserializeExpected<Value>(nullptr, *encoded);
        expect_true(decoded && decoded->number == index, "bounded typed codec workload must round-trip");
    }
    std::cout << "Typed JSON codec work: operations=" << operation_count << " encodes=" << work->encodes
              << " decodes=" << work->decodes << " registry=" << CTypes::codecCount() << '\n';
    expect_true(work->encodes == operation_count && work->decodes == operation_count,
                "one codec invocation is permitted per encode/decode operation");
    expect_true(CTypes::codecCount() == registered, "codec execution must never mutate registry entries");
}

class EffectSerializationProbe : public CCreature {
    V_META(EffectSerializationProbe, CCreature,
           V_PROPERTY(EffectSerializationProbe, int, serializationVisit, getSerializationVisit, setSerializationVisit))

  public:
    int getSerializationVisit() {
        ++serializationVisits;
        return 1;
    }

    void setSerializationVisit(int) {}

    static inline std::size_t serializationVisits = 0;
};

class MapLoadNotificationProbe : public CMapObject {
    V_META(MapLoadNotificationProbe, CMapObject,
           V_METHOD(MapLoadNotificationProbe, onPropertyChanged, void, std::string),
           V_METHOD(MapLoadNotificationProbe, onPropertiesChanged, void, std::set<std::string>))

  public:
    void onPropertyChanged(std::string) { ++property_changed_calls; }

    void onPropertiesChanged(std::set<std::string> property_names) {
        ++properties_changed_calls;
        changed_property_batches.push_back(std::move(property_names));
    }

    int property_changed_calls = 0;
    int properties_changed_calls = 0;
    std::vector<std::set<std::string>> changed_property_batches;
};

void drain_event_loop() {
    auto loop = vstd::event_loop<>::instance();
    for (int i = 0; i < 5; ++i) {
        loop->run();
    }
}

void connect_notifications(const std::shared_ptr<MapLoadNotificationProbe> &object) {
    object->connect("propertyChanged", object, "onPropertyChanged");
    object->connect("propertiesChanged", object, "onPropertiesChanged");
}

json make_observed_object_json(int index) {
    json object = json::object();
    object["type"] = "MapLoadNotificationProbe";
    object["name"] = "observedObject" + std::to_string(index);
    object["width"] = 16;
    object["height"] = 16;
    object["x"] = 16 * (index % 8);
    object["y"] = 16 * (index / 8);

    auto &properties = object["properties"];
    properties["label"] = "observed";
    properties["description"] = "bulk-loaded";
    properties["threat"] = index;
    properties["rank"] = index % 4;
    properties["active"] = true;
    properties["phase"] = "load";
    properties["score"] = index * 3;
    properties["visible"] = false;
    return object;
}

std::shared_ptr<json> make_map_json() {
    auto map_config = std::make_shared<json>(json::object());
    json layer = json::object();
    layer["type"] = "objectgroup";
    layer["properties"]["level"] = 0;
    layer["objects"] = json::array();
    for (int i = 0; i < MAP_LOAD_OBJECT_COUNT; ++i) {
        layer["objects"][layer["objects"].size()] = make_observed_object_json(i);
    }
    (*map_config)["layers"] = json::array({layer});
    return map_config;
}

void test_map_load_property_notifications_are_bounded_per_object() {
    CTypes::register_type_metadata<MapLoadNotificationProbe, CMapObject, CGameObject>();

    auto game = std::make_shared<CGame>();
    auto map = std::make_shared<CMap>();
    map->setGame(game);
    game->setMap(map);

    std::vector<std::shared_ptr<MapLoadNotificationProbe>> objects;
    objects.reserve(MAP_LOAD_OBJECT_COUNT);
    for (int i = 0; i < MAP_LOAD_OBJECT_COUNT; ++i) {
        auto object = std::make_shared<MapLoadNotificationProbe>();
        connect_notifications(object);
        objects.push_back(object);
    }

    std::size_t next_object = 0;
    game->getObjectHandler()->registerType("MapLoadNotificationProbe", [&objects, &next_object]() {
        if (next_object >= objects.size()) {
            return std::make_shared<MapLoadNotificationProbe>();
        }
        return objects[next_object++];
    });

    CMapLoader::loadFromTmx(map, make_map_json());
    drain_event_loop();

    int property_changed_calls = 0;
    int properties_changed_calls = 0;
    int changed_property_names = 0;
    for (const auto &object : objects) {
        property_changed_calls += object->property_changed_calls;
        properties_changed_calls += object->properties_changed_calls;
        for (const auto &batch : object->changed_property_batches) {
            changed_property_names += static_cast<int>(batch.size());
        }
    }

    expect_true(next_object == objects.size(), "map load should instantiate every observed object");
    expect_true(map->getObjects().size() == static_cast<std::size_t>(MAP_LOAD_OBJECT_COUNT),
                "map load should add every observed object to the map");
    expect_true(property_changed_calls == 0,
                "bulk map object property load should suppress per-property notifications");
    expect_true(properties_changed_calls == MAP_LOAD_OBJECT_COUNT,
                "bulk map object property load should emit one batch notification per object");
    expect_true(changed_property_names == MAP_LOAD_OBJECT_COUNT * MAP_LOAD_PROPERTY_COUNT,
                "bulk map object property load should preserve every changed property name in batches");
}

std::size_t countSerializedCreatures(const json &value) {
    std::size_t count = 0;
    if (value.is_object() && value.value("class", std::string()) == "EffectSerializationProbe" &&
        value.contains("properties")) {
        ++count;
    }
    if (value.is_object()) {
        for (const auto &[key, child] : value.items()) {
            count += countSerializedCreatures(child);
        }
    } else if (value.is_array()) {
        for (const auto &child : value) {
            count += countSerializedCreatures(child);
        }
    }
    return count;
}

void testMutualEffectGraphSerializationHasBoundedActorDefinitions() {
    CTypes::register_type<CGameObject>();
    CTypes::register_type<CMapObject, CGameObject>();
    CTypes::register_type<CMap, CGameObject>();
    CTypes::register_type<CCreature, CMapObject, CGameObject>();
    CTypes::register_type<EffectSerializationProbe, CCreature, CMapObject, CGameObject>();
    CTypes::register_type<CEffect, CGameObject>();
    CTypes::register_type<CStats, CGameObject>();
    CTypes::register_type<CController, CGameObject>();
    auto game = std::make_shared<CGame>();
    for (const auto &[name, builder] : *CTypes::builders()) {
        game->getObjectHandler()->registerType(name, builder);
    }
    auto map = std::make_shared<CMap>();
    map->setGame(game);
    game->setMap(map);
    std::vector<std::shared_ptr<CCreature>> actors;
    for (int index = 0; index <= EFFECT_GRAPH_ACTOR_COUNT; ++index) {
        auto actor = std::make_shared<EffectSerializationProbe>();
        actor->setGame(game);
        actor->setName("effectActor" + std::to_string(index));
        actor->setLevel(1);
        actor->setHp(10);
        actors.push_back(actor);
    }
    std::set<std::shared_ptr<CMapObject>> map_actors(actors.begin(), actors.end() - 1);
    map->setObjects(map_actors);
    for (int index = 0; index < EFFECT_GRAPH_ACTOR_COUNT; ++index) {
        for (int kind = 0; kind < 2; ++kind) {
            auto effect = std::make_shared<CEffect>();
            effect->setGame(game);
            effect->setName(kind == 0 ? "mutualWard" : "detachedWard");
            effect->setDuration(6);
            effect->getBonus()->setArmor(3);
            effect->setCaster(kind == 0 ? actors[(index + 1) % EFFECT_GRAPH_ACTOR_COUNT] : actors.back());
            effect->setVictim(actors[index]);
            effect->apply(actors[index]);
            actors[index]->addEffect(effect);
        }
    }

    using ObjectJson = CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>;
    EffectSerializationProbe::serializationVisits = 0;
    auto serialized = ObjectJson::serialize(map);
    const auto definitions = countSerializedCreatures(*serialized);
    const auto visits = EffectSerializationProbe::serializationVisits;
    const auto bytes = serialized->dump().size();
    const auto max_bytes = EFFECT_GRAPH_BYTES_PER_ACTOR * actors.size();
    std::cout << "effect graph: actors=" << actors.size() << " definitions=" << definitions << " visits=" << visits
              << " bytes=" << bytes << " byteBudget=" << max_bytes << "\n";
    expect_true(definitions == actors.size(),
                "cyclic effects and repeated caster references must serialize exactly one definition per actor");
    expect_true(bytes <= max_bytes, "the fixed mutual-effect workload must remain within its serialized size budget");
    expect_true(visits == actors.size(),
                "each referenced actor's properties must be visited exactly once per snapshot");

    CSerialization::StrictScope strict;
    auto restored = std::dynamic_pointer_cast<CMap>(ObjectJson::deserialize(game, serialized, strict));
    expect_true(restored && restored->getObjects().size() == EFFECT_GRAPH_ACTOR_COUNT,
                "loading the effect graph must not add the detached caster to the map");
    std::shared_ptr<CCreature> detached;
    if (restored) {
        for (int index = 0; index < EFFECT_GRAPH_ACTOR_COUNT; ++index) {
            auto actor = std::dynamic_pointer_cast<CCreature>(restored->getObjectByName(actors[index]->getName()));
            auto next = restored->getObjectByName(actors[(index + 1) % EFFECT_GRAPH_ACTOR_COUNT]->getName());
            expect_true(actor && actor->getEffects().size() == 2, "every actor must retain both effects after loading");
            if (!actor) {
                continue;
            }
            for (const auto &effect : actor->getEffects()) {
                expect_true(effect->getVictim() == actor, "each restored effect must resolve its actual owning victim");
                expect_true(effect->getTimeLeft() == 5 && effect->getBonus()->getArmor() == 3,
                            "bounded serialization must retain active effect state");
                if (effect->getName() == "mutualWard") {
                    expect_true(effect->getCaster() == next, "mutual actor references must resolve without duplicates");
                } else {
                    if (!detached) {
                        detached = effect->getCaster();
                    }
                    expect_true(detached && effect->getCaster() == detached,
                                "all external effects must share the one restored detached caster");
                }
            }
        }
        for (const auto &object : restored->getObjects()) {
            if (auto actor = std::dynamic_pointer_cast<CCreature>(object)) {
                actor->setEffects({});
            }
        }
    }
    for (const auto &actor : actors) {
        actor->setEffects({});
    }
}

class TerminalSerializationProbe : public CPlayer {
    V_META(TerminalSerializationProbe, CPlayer,
           V_PROPERTY(TerminalSerializationProbe, int, serializationVisit, getSerializationVisit,
                      setSerializationVisit))

  public:
    int getSerializationVisit() {
        ++serializationVisits;
        return 1;
    }
    void setSerializationVisit(int) {}
    static inline std::size_t serializationVisits = 0;
};

std::size_t countTerminalActorDefinitions(const json &value) {
    std::size_t count = 0;
    if (value.is_object() && value.value("class", std::string()) == "TerminalSerializationProbe" &&
        value.contains("properties")) {
        ++count;
    }
    if (value.is_object()) {
        for (const auto &[key, child] : value.items()) {
            count += countTerminalActorDefinitions(child);
        }
    } else if (value.is_array()) {
        for (const auto &child : value) {
            count += countTerminalActorDefinitions(child);
        }
    }
    return count;
}

std::size_t countTerminalPlayerTriggers(const std::shared_ptr<CMap> &map) {
    std::size_t count = 0;
    for (const auto &trigger : map->getEventHandler()->getTriggers()) {
        if (trigger && trigger->getObject() == "player") {
            ++count;
        }
    }
    return count;
}

void testRetainedTerminalPlayerWorkIsBounded() {
    constexpr int LOOKUPS = 128;
    constexpr int SNAPSHOTS = 4;
    constexpr std::size_t ACTOR_DEFINITIONS = 1;
    // Reuse the existing per-owner graph budget for one map and one retained player.
    constexpr std::size_t BYTE_BUDGET = EFFECT_GRAPH_BYTES_PER_ACTOR * 2;
    CTypes::register_type<CGameObject>();
    CTypes::register_type<CMapObject, CGameObject>();
    CTypes::register_type<CMap, CGameObject>();
    CTypes::register_type<CCreature, CMapObject, CGameObject>();
    CTypes::register_type<CPlayer, CCreature, CMapObject, CGameObject>();
    CTypes::register_type<TerminalSerializationProbe, CPlayer, CCreature, CMapObject, CGameObject>();
    CTypes::register_type<CStats, CGameObject>();
    CTypes::register_type<CController, CGameObject>();
    CTypes::register_type<CPlayerController, CController, CGameObject>();
    CTypes::register_type<CFightController, CGameObject>();
    CTypes::register_type<CPlayerFightController, CFightController, CGameObject>();
    auto game = std::make_shared<CGame>();
    for (const auto &[name, builder] : *CTypes::builders()) {
        game->getObjectHandler()->registerType(name, builder);
    }
    auto map = std::make_shared<CMap>();
    map->setGame(game);
    game->setMap(map);
    map->setPermanentPlayerDeath(true);
    auto player = std::make_shared<TerminalSerializationProbe>();
    player->setGame(game);
    player->setName("player");
    player->setLevel(1);
    player->setHp(0);
    map->setDefeatedPlayer(player);
    map->setObjectProperty<CGameObject>("terminalPlayerAlias", player);
    std::string error;
    expect_true(map->restorePlayerAfterLoad(error),
                "the terminal budget must begin with one valid retained dead player");
    const auto revision = map->getNavigationRevision();
    const auto objects = map->getObjects().size();
    const auto triggers = countTerminalPlayerTriggers(map);
    TerminalSerializationProbe::serializationVisits = 0;
    for (int repeat = 0; repeat < LOOKUPS; ++repeat) {
        expect_true(map->getPlayer() == player, "terminal lookups must reuse the exact retained identity");
    }
    expect_true(!player->isAlive() && !map->getObjectByName("player") && objects == 0 &&
                    map->getObjects().size() == objects && map->getNavigationRevision() == revision &&
                    countTerminalPlayerTriggers(map) == triggers &&
                    TerminalSerializationProbe::serializationVisits == 0,
                "128 cached terminal lookups must add no registry, navigation, trigger or serialization work");
    using ObjectJson = CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>;
    std::size_t max_bytes = 0;
    for (int snapshot = 0; snapshot < SNAPSHOTS; ++snapshot) {
        const auto visits_before = TerminalSerializationProbe::serializationVisits;
        auto document = ObjectJson::serialize(map);
        const auto definitions = countTerminalActorDefinitions(*document);
        const auto bytes = document->dump().size();
        max_bytes = std::max(max_bytes, bytes);
        expect_true(definitions == ACTOR_DEFINITIONS &&
                        TerminalSerializationProbe::serializationVisits == visits_before + ACTOR_DEFINITIONS &&
                        bytes <= BYTE_BUDGET,
                    "each terminal snapshot must visit and define one retained actor within the fixed graph budget");
        CSerialization::StrictScope strict;
        auto restored = std::dynamic_pointer_cast<CMap>(ObjectJson::deserialize(game, document, strict));
        std::string restore_error;
        const bool valid = restored && restored->restorePlayerAfterLoad(restore_error);
        expect_true(valid, "every bounded terminal snapshot must restore without resurrection");
        if (!valid) {
            continue;
        }
        auto actual = restored->getPlayer();
        const auto restored_revision = restored->getNavigationRevision();
        const auto restored_triggers = countTerminalPlayerTriggers(restored);
        for (int repeat = 0; repeat < LOOKUPS; ++repeat) {
            expect_true(restored->getPlayer() == actual,
                        "restored terminal lookups must reuse their captured identity");
        }
        expect_true(actual && !actual->isAlive() && restored->getDefeatedPlayer() == actual &&
                        restored->getObjectProperty<CGameObject>("terminalPlayerAlias") == actual &&
                        !restored->getObjectByName("player") && restored->getObjects().empty() &&
                        restored->getNavigationRevision() == restored_revision &&
                        countTerminalPlayerTriggers(restored) == restored_triggers,
                    "restored terminal lookup must preserve alias, empty registry, navigation and trigger counts");
    }
    expect_true(TerminalSerializationProbe::serializationVisits == SNAPSHOTS * ACTOR_DEFINITIONS,
                "the four snapshots must perform exactly four retained-player property visits");
    std::cout << "[performance] terminal player: lookups=" << LOOKUPS << " snapshots=" << SNAPSHOTS
              << " restoredLookups=" << LOOKUPS * SNAPSHOTS << " actorDefinitions=" << ACTOR_DEFINITIONS
              << " visits=" << TerminalSerializationProbe::serializationVisits << " maxBytes=" << max_bytes
              << " byteBudget=" << BYTE_BUDGET << " objects=" << objects << " triggers=" << triggers << '\n';
    game->getContext()->shutdown();
}

} // namespace

void run_serialization_performance_tests() {
    testTypedCodecWorkIsBoundedPerOperation();
    test_map_load_property_notifications_are_bounded_per_object();
    testMutualEffectGraphSerializationHasBoundedActorDefinitions();
    testScalarPropertyMetadataWorkIsBounded();
    testRejectedSaveAdmissionHasZeroSnapshotWork();
    testSnapshotAdmissionRejectsEncountersBeforeMutation();
    testRetainedTerminalPlayerWorkIsBounded();
}
