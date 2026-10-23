/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026 Andrzej Lis
SPDX-License-Identifier: GPL-3.0-or-later
*/
#include "core/CController.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CLoader.h"
#include "core/CMap.h"
#include "core/CPlaytestTrace.h"
#include "core/CPythonOverrides.h"
#include "core/CStats.h"
#include "handler/CFightHandler.h"
#include "object/CCreature.h"
#include "object/CEffect.h"
#include "object/CInteraction.h"
#include "object/CItem.h"
#include "object/CPlayer.h"
#include "test_harness.h"

#include <SDL.h>
#include <pybind11/embed.h>
#include <cmath>
#include <functional>
#include <memory>
#include <string>
#include <vector>

extern "C" PyObject *PyInit__game();

namespace {
void initializeAlliedCombatPythonContent() {
    auto sys = pybind11::module_::import("sys");
    sys.attr("path").attr("insert")(0, GAME_ALLIED_COMBAT_TEST_RESOURCE_ROOT);
    pybind11::module_::import("_game");
    pybind11::module_::import("game");
    pybind11::module_::import("json");
}

class ProbeController : public CFightController {
  public:
    int starts = 0;
    int ends = 0;
    int actions = 0;
    bool cancelled = false;
    std::function<void(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>)> action;

    void start(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override { ++starts; }
    void end(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override { ++ends; }
    bool isCancelled(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override { return cancelled; }
    bool control(std::shared_ptr<CCreature> actor, std::shared_ptr<CCreature> target) override {
        ++actions;
        if (action) {
            action(actor, target);
        }
        return true;
    }
};

// This native-only executable does not initialize the configured Python Attack plugin.
// Exercise interaction selection, dispatch and native damage with an explicit native test action.
class NativeAttackProbe : public CInteraction {
  public:
    int calls = 0;
    void performAction(std::shared_ptr<CCreature> actor, std::shared_ptr<CCreature> target) override {
        ++calls;
        target->hurt(actor->getDmg());
    }
};

class CountingMonsterController : public CMonsterFightController {
  public:
    int actions = 0;
    vstd::task<bool> controlAsync(std::shared_ptr<CCreature> actor, std::shared_ptr<CCreature> target) override {
        ++actions;
        co_return co_await CMonsterFightController::controlAsync(std::move(actor), std::move(target));
    }
};

void initializeStats(const std::shared_ptr<CCreature> &actor, int agility = 10) {
    actor->setBaseStats(std::make_shared<CStats>());
    actor->setLevelStats(std::make_shared<CStats>());
    auto stats = actor->getBaseStats();
    stats->setMainStat("strength");
    stats->setStrength(10);
    stats->setStamina(10);
    stats->setAgility(agility);
    stats->setHit(100);
    stats->setDmgMin(10);
    stats->setDmgMax(10);
    stats->setCrit(0);
    actor->setLevel(1);
    actor->setSw(-5);
    actor->setHp(70);
    actor->setMana(70);
}

struct Fixture {
    std::shared_ptr<CGame> game = CGameLoader::loadGame();
    std::shared_ptr<CMap> map;
    std::shared_ptr<CPlayer> hero;
    std::shared_ptr<ProbeController> heroController = std::make_shared<ProbeController>();

    Fixture() {
        CGameLoader::startGame(game, "empty");
        map = game->getMap();
        hero = std::make_shared<CPlayer>();
        hero->setGame(game);
        initializeStats(hero);
        hero->setAffiliation("cityParty");
        map->setPlayer(hero);
        hero->setFightController(heroController);
        hero->setHp(70);
        hero->relocateWithoutMoveHooks(Coords(0, 0, 0));
    }
    ~Fixture() { game->getContext()->shutdown(); }

    std::shared_ptr<CCreature> actor(const std::string &name, bool allied = false, int x = 1, int agility = 10) {
        auto creature = std::make_shared<CCreature>();
        creature->setGame(game);
        creature->setName(name);
        initializeStats(creature, agility);
        creature->setPosX(x);
        creature->setAffiliation(allied ? "cityParty" : "cityHostiles");
        creature->setFightController(std::make_shared<ProbeController>());
        map->addObject(creature);
        creature->setHp(70);
        return creature;
    }

    std::shared_ptr<CItem> possession(const std::shared_ptr<CCreature> &owner, const std::string &name) {
        auto item = std::make_shared<CItem>();
        item->setGame(game);
        item->setName(name);
        item->setTypeId(name);
        owner->addItem(item);
        return item;
    }

    void enable(const std::string &names) {
        map->setBoolProperty("plugin_cityAlliedCombat", true);
        map->setStringProperty("plugin_cityCompanionNames", names);
    }
};

std::shared_ptr<ProbeController> probe(const std::shared_ptr<CCreature> &actor) {
    return std::dynamic_pointer_cast<ProbeController>(actor->getFightController());
}

void testNativeAllyActsAndHeroOwnsRewards() {
    Fixture fixture;
    auto ally = fixture.actor("nativeAlly", true, 0, 20);
    auto enemy = fixture.actor("nativeEnemy");
    enemy->setHp(1);
    auto item = fixture.possession(enemy, "uniqueCityQuestReward");
    item->addTag("quest");
    auto controller = std::make_shared<CountingMonsterController>();
    ally->setFightController(controller);
    auto attack = std::make_shared<NativeAttackProbe>();
    attack->setGame(fixture.game);
    attack->setName("nativeTestAttack");
    attack->setTypeId("Attack");
    ally->addAction(attack);
    const auto expectedXp = static_cast<int>(250 * std::pow(2.0, enemy->getScale() - fixture.hero->getLevel()));
    const auto initialXp = fixture.hero->getExp();
    CPlaytestTrace::configure(true, "", 128, true);
    const auto result = CFightHandler::fightManyWithAlliesResult(fixture.hero, {enemy}, {ally});
    bool witnessedAction = false;
    for (const auto &line : CPlaytestTrace::drain()) {
        const auto record = json::parse(line);
        if (record.value("event", std::string()) == "combat_ally_acted") {
            witnessedAction = record.at("actor").at("name").get<std::string>() == ally->getName();
        }
    }
    CPlaytestTrace::configure(false);
    expect_true(result.outcome == CFightOutcome::AttackerVictory && result.survivor == fixture.hero,
                "an actual native ally attack must resolve the hero-side encounter");
    expect_true(controller->actions == 1 && attack->calls == 1 && witnessedAction &&
                    fixture.heroController->actions == 0,
                "the native ally must act rather than only receiving a participation flag");
    expect_true(fixture.hero->hasInInventory(item) && !ally->hasInInventory(item) &&
                    fixture.hero->getExp() == initialXp + expectedXp,
                "allied enemy kills must give the hero the actual unique item and exact native XP");
}

void testRegisteredPythonAllyActsAndHeroOwnsRewards() {
    Fixture fixture;
    auto ally = fixture.actor("nativeAlly", true, 0, 20);
    auto enemy = fixture.actor("nativeEnemy");
    enemy->setHp(1);
    auto item = fixture.possession(enemy, "uniqueCityQuestReward");
    item->addTag("quest");
    auto controller = std::make_shared<CountingMonsterController>();
    ally->setFightController(controller);
    auto attack = fixture.game->createObject<CInteraction>("Attack");
    expect_true(attack && !CPythonOverrides::find_override(attack.get(), "performAction").is_none(),
                "the native ally must execute the real registered Python Attack action");
    ally->addAction(attack);
    const auto expectedXp = static_cast<int>(250 * std::pow(2.0, enemy->getScale() - fixture.hero->getLevel()));
    const auto initialXp = fixture.hero->getExp();
    CPlaytestTrace::configure(true, "", 128, true);
    const auto result = CFightHandler::fightManyWithAlliesResult(fixture.hero, {enemy}, {ally});
    bool witnessedAction = false;
    for (const auto &line : CPlaytestTrace::drain()) {
        const auto record = json::parse(line);
        if (record.value("event", std::string()) == "combat_ally_acted") {
            witnessedAction = record.at("actor").at("name").get<std::string>() == ally->getName();
        }
    }
    CPlaytestTrace::configure(false);
    expect_true(result.outcome == CFightOutcome::AttackerVictory && result.survivor == fixture.hero,
                "the registered Python ally attack must resolve the hero-side encounter");
    expect_true(controller->actions == 1 && witnessedAction &&
                    fixture.heroController->actions == 0,
                "the registered Python ally must act rather than only receiving a participation flag");
    expect_true(fixture.hero->hasInInventory(item) && !ally->hasInInventory(item) &&
                    fixture.hero->getExp() == initialXp + expectedXp,
                "allied enemy kills must give the hero the actual unique item and exact native XP");
}

void testAlliedBudgetAndRejectedParticipants() {
    Fixture fixture;
    Fixture other;
    auto enemy = fixture.actor("budgetEnemy");
    auto foreign = other.actor("foreignAlly", true);
    auto stale = fixture.actor("staleAlly", true);
    fixture.map->removeObject(stale);
    auto dead = fixture.actor("deadAlly", true);
    dead->setHp(0);
    auto upstairs = fixture.actor("upstairsAlly", true);
    upstairs->setPosZ(1);
    auto hostile = fixture.actor("hostileNonAlly");
    auto uiAlly = fixture.actor("uiAlly", true);
    uiAlly->setFightController(std::make_shared<CPlayerFightController>());
    std::vector<std::shared_ptr<CCreature>> candidates = {nullptr,  fixture.hero, foreign, stale, dead,
                                                          upstairs, hostile,      uiAlly,  enemy};
    std::vector<std::shared_ptr<ProbeController>> accepted;
    for (int index = 0; index < 6; ++index) {
        auto ally = fixture.actor("budgetAlly" + std::to_string(index), true);
        candidates.push_back(ally);
        candidates.push_back(ally);
        accepted.push_back(probe(ally));
    }
    const auto result = CFightHandler::fightManyWithAlliesResult(fixture.hero, {enemy}, candidates);
    int actions = 0;
    for (std::size_t index = 0; index < accepted.size(); ++index) {
        const auto &controller = accepted[index];
        actions += controller->actions;
        expect_true(index < CFightHandler::MaximumAllies
                        ? controller->starts == 1 && controller->ends == 1 && controller->actions == 20
                        : controller->starts == 0 && controller->ends == 0 && controller->actions == 0,
                    "only five distinct eligible allies may enter an encounter");
    }
    expect_true(result.outcome == CFightOutcome::Stalled && result.rounds == 20 && actions == 100,
                "no-progress allied combat must obey exactly five allies times twenty bounded rounds");
    expect_true(probe(foreign)->starts == 0 && probe(stale)->starts == 0 && probe(dead)->starts == 0 &&
                    probe(upstairs)->starts == 0 && probe(hostile)->starts == 0,
                "cross-map, removed, dead, other-level and hostile actors must not receive ally turns");
}

void testExplicitCandidatesBeyondNaturalDiscoveryBudget() {
    Fixture fixture;
    auto ally = fixture.actor("lateExplicitAlly", true, 0, 20);
    auto enemy = fixture.actor("lateExplicitEnemy");
    probe(ally)->action = [](auto, auto target) { target->setHp(0); };
    std::vector<std::shared_ptr<CCreature>> candidates(32, nullptr);
    candidates.insert(candidates.end(), 32, fixture.hero);
    candidates.push_back(ally);
    const auto result = CFightHandler::fightManyWithAlliesResult(fixture.hero, {enemy}, candidates);
    expect_true(result.outcome == CFightOutcome::AttackerVictory && probe(ally)->actions == 1,
                "explicit candidates must find a valid ally after invalid entries beyond thirty-two names");

    Fixture natural;
    auto naturalAlly = natural.actor("lateNaturalAlly", true, 0, 20);
    auto naturalEnemy = natural.actor("lateNaturalEnemy");
    probe(naturalAlly)->action = [](auto, auto target) { target->setHp(0); };
    std::string names;
    for (int index = 0; index < 32; ++index) {
        names += "missingAlly,";
    }
    natural.enable(names + naturalAlly->getName());
    expect_true(CFightHandler::fightManyResult(natural.hero, {naturalEnemy}).outcome == CFightOutcome::Stalled &&
                    probe(naturalAlly)->starts == 0,
                "natural discovery must still stop after thirty-two configured names");
}

void testNaturalOptInAndMoverPerspectives() {
    for (int mover = 0; mover < 3; ++mover) {
        Fixture fixture;
        auto ally = fixture.actor("configuredAlly", true, 0, 20);
        auto enemy = fixture.actor("configuredEnemy");
        probe(ally)->action = [](auto, auto target) { target->setHp(0); };
        const auto legacy = CFightHandler::fightManyResult(fixture.hero, {enemy});
        expect_true(legacy.outcome == CFightOutcome::Stalled && probe(ally)->starts == 0,
                    "an existing map must not implicitly recruit nearby friendly creatures");
        fixture.enable("configuredAlly,configuredAlly");
        auto initiator = mover == 0 ? std::shared_ptr<CCreature>(fixture.hero) : mover == 1 ? ally : enemy;
        std::vector<std::shared_ptr<CCreature>> targets = {mover == 2 ? ally : enemy};
        const auto result = CFightHandler::fightManyResult(initiator, targets);
        expect_true(
            result.outcome == (mover == 2 ? CFightOutcome::AttackerDefeat : CFightOutcome::AttackerVictory),
            "configured allies must support hero, follower and enemy initiated encounters in mover perspective");
        expect_true(probe(ally)->actions == 1 && fixture.map->getObjectByName(enemy->getName()) == nullptr,
                    "each opted-in collision must run the same real allied action");
    }
    Fixture fixture;
    auto ally = fixture.actor("distantAlly", true, 17, 20);
    auto enemy = fixture.actor("radiusEnemy");
    fixture.enable("distantAlly");
    fixture.map->setNumericProperty("plugin_cityCompanionCombatRadius", 1000);
    expect_true(CFightHandler::fightManyResult(fixture.hero, {enemy}).outcome == CFightOutcome::Stalled &&
                    probe(ally)->starts == 0,
                "the map-local companion radius must remain capped at sixteen tiles");
}

void testFallenAllyUsesNativeLootAndSurvivorsContinue() {
    Fixture fixture;
    auto ally = fixture.actor("fallenAlly", true, 2, 1);
    auto enemy = fixture.actor("allyKiller", false, 2, 30);
    auto item = fixture.possession(ally, "fallenAllyPossession");
    auto allyController = probe(ally);
    probe(enemy)->action = [&](auto, auto target) {
        if (target != fixture.hero) {
            target->setHp(0);
        }
    };
    const auto result = CFightHandler::fightManyWithAlliesResult(fixture.hero, {enemy}, {ally});
    expect_true(result.outcome == CFightOutcome::Stalled && fixture.hero->isAlive() &&
                    fixture.map->getObjectByName(ally->getName()) == nullptr,
                "a follower death must destroy that actor while the living hero encounter continues");
    expect_true(enemy->hasInInventory(item) && !ally->hasInInventory(item) && allyController->actions == 0 &&
                    allyController->starts == 1 && allyController->ends == 1,
                "the actual enemy winner must receive fallen follower loot and its original controller must end");
}

void testHeroDefeatEndsBeforeSurvivingAlliesAct() {
    Fixture fixture;
    auto ally = fixture.actor("survivingAlly", true, 2, 1);
    auto enemy = fixture.actor("heroKiller", false, 0, 30);
    auto item = fixture.possession(fixture.hero, "heroLostPossession");
    probe(enemy)->action = [](auto, auto target) { target->setHp(0); };
    const auto result = CFightHandler::fightManyWithAlliesResult(fixture.hero, {enemy}, {ally});
    expect_true(result.outcome == CFightOutcome::AttackerDefeat && result.rounds == 1 && result.survivor == enemy,
                "native hero respawn must not turn a defeated party encounter into a later allied victory");
    expect_true(fixture.hero->isAlive() && fixture.hero->getHp() == 1 && ally->isAlive() && probe(ally)->actions == 0 &&
                    enemy->hasInInventory(item),
                "surviving allies must remain actors while native hero defeat/loot semantics complete once");
}

void testCancelledAndStaleAlliedEncountersEndControllers() {
    for (bool changeMap : {false, true}) {
        Fixture fixture;
        auto ally = fixture.actor("cancelAlly", true, 0, 30);
        auto enemy = fixture.actor("cancelEnemy");
        auto allyController = probe(ally);
        if (changeMap) {
            allyController->action = [&](auto, auto) {
                auto next = std::make_shared<CMap>();
                next->setGame(fixture.game);
                fixture.game->setMap(next);
            };
        } else {
            allyController->cancelled = true;
        }
        const auto result = CFightHandler::fightManyWithAlliesResult(fixture.hero, {enemy}, {ally});
        expect_true(result.outcome == CFightOutcome::Cancelled && allyController->starts == 1 &&
                        allyController->ends == 1 && fixture.heroController->starts == 1 &&
                        fixture.heroController->ends == 1 && probe(enemy)->starts == 1 && probe(enemy)->ends == 1,
                    "cancellation and map changes must end every original controller exactly once");
        expect_true(allyController->actions == 1 && probe(enemy)->actions == 0 && enemy->isAlive(),
                    "a stale or cancelled ally action must not allow later encounter actors to execute");
    }
    Fixture fixture;
    auto ally = fixture.actor("removedAlly", true, 0, 1);
    auto enemy = fixture.actor("removingEnemy", false, 1, 30);
    auto controller = probe(ally);
    probe(enemy)->action = [&](auto, auto) { fixture.map->removeObject(ally); };
    const auto result = CFightHandler::fightManyWithAlliesResult(fixture.hero, {enemy}, {ally});
    expect_true(result.outcome == CFightOutcome::Stalled && controller->actions == 0 && controller->ends == 1,
                "an ally removed before its initiative turn must never act through the old snapshot");
}

void testFixedCityLootTransfersGoldAndEquippedPossessionsOnce() {
    Fixture fixture;
    fixture.map->setBoolProperty("plugin_cityFixedLoot", true);
    auto enemy = fixture.actor("sourceOwner");
    auto carried = fixture.possession(enemy, "sourceCarriedReward");
    auto protectedItem = fixture.possession(enemy, "sourceForbiddenDrop");
    protectedItem->setBoolProperty("plugin_cityUndroppable", true);
    auto equipped = std::make_shared<CWeapon>();
    equipped->setGame(fixture.game);
    equipped->setName("sourceEquippedSword");
    equipped->setTypeId("sourceEquippedSword");
    equipped->addTag("cursed");
    enemy->setEquipped({{"0", equipped}});
    enemy->setGold(37);
    enemy->setHp(0);
    const int before = fixture.hero->getGold();
    CFightHandler::defeatedCreature(fixture.hero, enemy);
    expect_true(fixture.hero->getGold() == before + 37 && enemy->getGold() == 0,
                "fixed city loot must transfer the defeated NPC's actual gold once");
    expect_true(fixture.hero->getInInventory().size() == 2 && fixture.hero->hasInInventory(carried) &&
                    fixture.hero->hasInInventory(equipped) && !enemy->hasItem(carried) && !enemy->hasItem(equipped),
                "fixed city loot must transfer actual bag and equipped objects without random additions or old owners");
    expect_true(enemy->hasInInventory(protectedItem) && !fixture.hero->hasInInventory(protectedItem),
                "a source-forbidden drop must remain with the removed actor, including any retained corpse reference");
    const int afterXp = fixture.hero->getExp();
    CFightHandler::defeatedCreature(fixture.hero, enemy);
    expect_true(fixture.hero->getGold() == before + 37 && fixture.hero->getExp() == afterXp &&
                    fixture.hero->getInInventory().size() == 2,
                "repeating defeated-creature cleanup must not duplicate source gold, items or experience");
}

void testAllyEffectsCountAsEncounterProgress() {
    Fixture fixture;
    auto ally = fixture.actor("effectAlly", true);
    auto enemy = fixture.actor("effectEnemy");
    auto effect = std::make_shared<CEffect>();
    effect->setGame(fixture.game);
    effect->setName("countdownEffect");
    effect->setDuration(25);
    ally->addEffect(effect);
    const auto result = CFightHandler::fightManyWithAlliesResult(fixture.hero, {enemy}, {ally});
    expect_true(result.outcome == CFightOutcome::Stalled && result.rounds > 40 && result.rounds <= 100 &&
                    ally->getEffects().empty(),
                "real allied effect ticks must count as progress without removing bounded encounter termination");
}
} // namespace

int main() {
    if (PyImport_AppendInittab("_game", PyInit__game) != 0) {
        std::cerr << "Cannot register the real embedded _game module\n";
        return 1;
    }
    pybind11::scoped_interpreter interpreter{};
    initializeAlliedCombatPythonContent();
    testNativeAllyActsAndHeroOwnsRewards();
    testRegisteredPythonAllyActsAndHeroOwnsRewards();
    testAlliedBudgetAndRejectedParticipants();
    testExplicitCandidatesBeyondNaturalDiscoveryBudget();
    testNaturalOptInAndMoverPerspectives();
    testFallenAllyUsesNativeLootAndSurvivorsContinue();
    testHeroDefeatEndsBeforeSurvivingAlliesAct();
    testCancelledAndStaleAlliedEncountersEndControllers();
    testAllyEffectsCountAsEncounterProgress();
    testFixedCityLootTransfersGoldAndEquippedPossessionsOnce();
    return finish_tests();
}
