/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026 Andrzej Lis
SPDX-License-Identifier: GPL-3.0-or-later
*/
#include "core/CAsync.h"
#include "core/CController.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CLoader.h"
#include "core/CMap.h"
#include "core/CPlaytestTrace.h"
#include "core/CPythonOverrides.h"
#include "core/CStats.h"
#include "core/CTypes.h"
#include "handler/CFightHandler.h"
#include "object/CCreature.h"
#include "object/CEffect.h"
#include "object/CInteraction.h"
#include "object/CItem.h"
#include "object/CPlayer.h"
#include "object/CQuest.h"
#include "object/CTile.h"
#include "test_harness.h"

#include <SDL.h>
#include <pybind11/embed.h>
#include <cmath>
#include <functional>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
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

    std::function<void()> starting;
    std::function<void()> ending;

    void start(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override {
        ++starts;
        if (starting) {
            starting();
        }
    }
    void end(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override {
        ++ends;
        if (ending) {
            ending();
        }
    }
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

void testCombatCleanupExceptionsEndEveryControllerOnce() {
    Fixture fixture;
    fixture.hero->getBaseStats()->setAgility(30);
    auto enemy = fixture.actor("cleanupEnemy");
    auto ally = fixture.actor("cleanupAlly", true);
    const auto enemyController = probe(enemy);
    const auto allyController = probe(ally);
    fixture.heroController->action = [&](auto, auto) { fixture.heroController->cancelled = true; };
    fixture.heroController->ending = [] { throw std::runtime_error("first cleanup failure"); };
    enemyController->ending = [] { throw std::runtime_error("second cleanup failure"); };
    bool firstFailure = false;
    try {
        CFightHandler::fightManyWithAlliesResult(fixture.hero, {enemy}, {ally});
    } catch (const std::runtime_error &failure) {
        firstFailure = std::string(failure.what()) == "first cleanup failure";
    }
    expect_true(firstFailure && fixture.heroController->actions == 1 && enemyController->actions == 0 &&
                    allyController->actions == 0,
                "explicit finish must report its first cleanup failure after an ordinary encounter is cancelled");
    expect_true(fixture.heroController->starts == 1 && enemyController->starts == 1 && allyController->starts == 1 &&
                    fixture.heroController->ends == 1 && enemyController->ends == 1 && allyController->ends == 1,
                "every owned controller must end once even when multiple cleanup hooks throw");
}

void testCombatCleanupPreservesPrimaryFailureAndCancellation() {
    for (const bool cancelled : {false, true}) {
        Fixture fixture;
        fixture.hero->getBaseStats()->setAgility(30);
        auto enemy = fixture.actor("primaryFailureEnemy");
        auto ally = fixture.actor("primaryFailureAlly", true);
        const auto enemyController = probe(enemy);
        const auto allyController = probe(ally);
        fixture.heroController->action = [cancelled](auto, auto) {
            if (cancelled) {
                throw vstd::task_cancelled();
            }
            throw std::runtime_error("primary combat failure");
        };
        fixture.heroController->ending = [] { throw std::runtime_error("first cleanup failure"); };
        enemyController->ending = [] { throw std::runtime_error("second cleanup failure"); };
        bool originalFailure = false;
        try {
            auto task = CFightHandler::fightManyWithAlliesResultAsync(fixture.hero, {enemy}, {ally});
            game_async::wait(fixture.game->getContext()->spawnTask(std::move(task)), game_async::WaitMode::PostedWork);
        } catch (const vstd::task_cancelled &) {
            originalFailure = cancelled;
        } catch (const std::runtime_error &failure) {
            originalFailure = !cancelled && std::string(failure.what()) == "primary combat failure";
        }
        expect_true(originalFailure && fixture.heroController->actions == 1 && enemyController->actions == 0 &&
                        allyController->actions == 0,
                    "cleanup must preserve the original native combat or cancellation exception");
        expect_true(fixture.heroController->ends == 1 && enemyController->ends == 1 && allyController->ends == 1,
                    "unwinding must attempt every original controller end exactly once");
    }
}

void testCombatOwnsPartialControllerStartsAndPreservesTheirFailure() {
    for (const bool firstFails : {false, true}) {
        Fixture fixture;
        auto enemy = fixture.actor("partialStartEnemy");
        auto ally = fixture.actor("neverStartedAlly", true);
        const auto enemyController = probe(enemy);
        const auto allyController = probe(ally);
        bool resourceAcquired = false;
        const auto failingController = firstFails ? fixture.heroController : enemyController;
        failingController->starting = [&] {
            resourceAcquired = true;
            throw std::runtime_error("primary start failure");
        };
        fixture.heroController->ending = [&] {
            if (firstFails) {
                resourceAcquired = false;
            }
            throw std::runtime_error("hero cleanup failure");
        };
        enemyController->ending = [&] {
            if (!firstFails) {
                resourceAcquired = false;
            }
            throw std::runtime_error("enemy cleanup failure");
        };
        bool originalFailure = false;
        try {
            CFightHandler::fightManyWithAlliesResult(fixture.hero, {enemy}, {ally});
        } catch (const std::runtime_error &failure) {
            originalFailure = std::string(failure.what()) == "primary start failure";
        }
        expect_true(originalFailure && !resourceAcquired && fixture.heroController->starts == 1 &&
                        fixture.heroController->ends == 1 && enemyController->starts == (firstFails ? 0 : 1) &&
                        enemyController->ends == (firstFails ? 0 : 1),
                    "partial initialization must be owned for cleanup without masking its start failure");
        expect_true(allyController->starts == 0 && allyController->ends == 0 && fixture.heroController->actions == 0 &&
                        enemyController->actions == 0 && allyController->actions == 0,
                    "admission must neither end unstarted controllers nor dispatch combat actions");
    }
}

void testRejectedCombatAdmissionDoesNotStartOrEndControllers() {
    Fixture fixture;
    auto ally = fixture.actor("unadmittedAlly", true);
    const auto result = CFightHandler::fightManyWithAlliesResult(fixture.hero, {}, {ally});
    expect_true(result.outcome == CFightOutcome::Invalid && fixture.heroController->starts == 0 &&
                    fixture.heroController->ends == 0 && probe(ally)->starts == 0 && probe(ally)->ends == 0,
                "an encounter rejected before controller startup must own no controller cleanup");
}

class EncounterAdmissionQuest : public CQuest {
  public:
    int captures = 0;
    void captureJournal(bool) override { ++captures; }
};

class EncounterAdmissionGraphProbe : public CGameObject {
    V_META(EncounterAdmissionGraphProbe, CGameObject,
           V_PROPERTY(EncounterAdmissionGraphProbe, int, graphVisit, getGraphVisit, setGraphVisit))
  public:
    int visits = 0;
    int getGraphVisit() {
        ++visits;
        throw std::runtime_error("intentional encounter snapshot stop before resource writes");
    }
    void setGraphVisit(int) {}
};

struct EncounterAdmissionWork {
    std::shared_ptr<CMap> map;
    std::shared_ptr<EncounterAdmissionQuest> quest = std::make_shared<EncounterAdmissionQuest>();
    std::shared_ptr<EncounterAdmissionGraphProbe> graph = std::make_shared<EncounterAdmissionGraphProbe>();
    int attempts = 0;

    explicit EncounterAdmissionWork(Fixture &fixture) : map(fixture.map) {
        CTypes::register_type<EncounterAdmissionGraphProbe, CGameObject>();
        quest->setGame(fixture.game);
        graph->setGame(fixture.game);
        fixture.hero->setQuests({quest});
        map->setObjectProperty("encounterAdmissionGraphProbe", graph);
    }
    void attempt() {
        ++attempts;
        expect_true(!CMapLoader::saveWithResult(map, "unit-encounter-admission-no-write"),
                    "an encounter save must reject or hit the intentional graph stop without writing");
    }
};

class EncounterAdmissionEffect : public CEffect {
  public:
    std::function<void()> callback;
    std::function<void()> formatting;
    void onEffect() override { callback(); }
    std::string to_string() override {
        if (formatting) {
            formatting();
        }
        return CEffect::to_string();
    }
};

class EncounterAdmissionCreature : public CCreature {
  public:
    std::function<void()> looting;
    std::function<void()> destroying;
    std::set<std::shared_ptr<CItem>> getAllItems() override {
        if (looting) {
            looting();
        }
        return CCreature::getAllItems();
    }
    void onDestroy(std::shared_ptr<CGameEvent> event) override {
        if (destroying) {
            destroying();
        }
        CCreature::onDestroy(std::move(event));
    }
};

void testDirectEncounterSaveAdmissionAndLegacyDefault() {
    for (const bool optedIn : {false, true}) {
        Fixture fixture;
        fixture.map->setBoolProperty("guardNativeEncounterSaves", optedIn);
        fixture.hero->getBaseStats()->setAgility(30);
        auto enemy = fixture.actor("saveBoundaryEnemy");
        EncounterAdmissionWork work(fixture);
        fixture.heroController->starting = [&] { work.attempt(); };
        probe(enemy)->starting = [&] { work.attempt(); };
        fixture.heroController->action = [&](auto, auto) {
            work.attempt();
            fixture.heroController->cancelled = true;
        };
        fixture.heroController->ending = [&] { work.attempt(); };
        probe(enemy)->ending = [&] { work.attempt(); };
        const auto result = CFightHandler::fightManyResult(fixture.hero, {enemy});
        const int expectedWork = optedIn ? 0 : 5;
        expect_true(result.outcome == CFightOutcome::Cancelled && work.attempts == 5 &&
                        work.quest->captures == expectedWork && work.graph->visits == expectedWork,
                    "direct ordinary combat must gate starts/action/ends only on explicitly opted-in maps");
        expect_true(fixture.heroController->ends == 1 && probe(enemy)->ends == 1 &&
                        fixture.map->tryBeginSaveSnapshot().has_value(),
                    "a normal returned outcome must finish admission only after every controller end succeeded");
    }
}

void testEncounterAdmissionSpansEffectsLootAndRemoval() {
    Fixture fixture;
    fixture.map->setBoolProperty("guardNativeEncounterSaves", true);
    fixture.map->setBoolProperty("plugin_cityFixedLoot", true);
    fixture.hero->getBaseStats()->setAgility(30);
    auto enemy = std::make_shared<EncounterAdmissionCreature>();
    enemy->setGame(fixture.game);
    enemy->setName("admittedTerminalEnemy");
    initializeStats(enemy);
    enemy->setAffiliation("cityHostiles");
    enemy->setFightController(std::make_shared<ProbeController>());
    fixture.map->addObject(enemy);
    enemy->setHp(1);
    auto item = fixture.possession(enemy, "admittedTerminalReward");
    EncounterAdmissionWork work(fixture);
    int effectCalls = 0;
    int lootCalls = 0;
    int removalCalls = 0;
    auto effect = std::make_shared<EncounterAdmissionEffect>();
    effect->setGame(fixture.game);
    effect->setDuration(2);
    effect->callback = [&] {
        ++effectCalls;
        work.attempt();
    };
    fixture.hero->addEffect(effect);
    enemy->looting = [&] {
        ++lootCalls;
        work.attempt();
    };
    enemy->destroying = [&] {
        ++removalCalls;
        work.attempt();
    };
    fixture.heroController->action = [](auto, auto target) { target->setHp(0); };
    fixture.heroController->ending = [&] { work.attempt(); };
    probe(enemy)->ending = [&] { work.attempt(); };
    const auto result = CFightHandler::fightManyResult(fixture.hero, {enemy});
    expect_true(result.outcome == CFightOutcome::AttackerVictory && effectCalls == 1 && lootCalls == 1 &&
                    removalCalls == 1 && work.attempts == 5 && work.quest->captures == 0 && work.graph->visits == 0,
                "actual effect/loot/removal and controller-end hooks must remain inside native admission");
    expect_true(fixture.hero->hasInInventory(item) && !fixture.map->getObjectByName(enemy->getName()) &&
                    fixture.map->tryBeginSaveSnapshot().has_value(),
                "admission must finish only after actual terminal loot/removal and successful ends have settled");
}

void testEncounterAdmissionQuarantinesPrimaryCleanupAndBindingFailures() {
    for (int mode = 0; mode < 5; ++mode) {
        Fixture fixture;
        fixture.map->setBoolProperty("guardNativeEncounterSaves", true);
        fixture.hero->getBaseStats()->setAgility(30);
        auto enemy = fixture.actor("quarantinedEncounterEnemy");
        EncounterAdmissionWork work(fixture);
        if (mode == 3) {
            fixture.heroController->starting = [&] {
                work.attempt();
                throw std::runtime_error("primary start failure");
            };
        }
        fixture.heroController->action = [&](auto, auto) {
            work.attempt();
            if (mode == 0) {
                throw std::runtime_error("primary action failure");
            }
            if (mode == 1) {
                throw vstd::task_cancelled();
            }
            if (mode == 4) {
                auto next = std::make_shared<CMap>();
                next->setGame(fixture.game);
                fixture.game->setMap(next);
            }
            fixture.heroController->cancelled = true;
        };
        fixture.heroController->ending = [&] {
            work.attempt();
            if (mode == 1 || mode == 2 || mode == 3) {
                throw std::runtime_error("first cleanup failure");
            }
        };
        probe(enemy)->ending = [&] {
            work.attempt();
            if (mode == 1 || mode == 2) {
                throw std::runtime_error("second cleanup failure");
            }
        };
        bool expectedFailure = false;
        try {
            auto task = CFightHandler::fightManyResultAsync(fixture.hero, {enemy});
            const auto result = game_async::wait(fixture.game->getContext()->spawnTask(std::move(task)),
                                                 game_async::WaitMode::PostedWork);
            expectedFailure = mode == 4 && result.outcome == CFightOutcome::Cancelled;
        } catch (const vstd::task_cancelled &) {
            expectedFailure = mode == 1;
        } catch (const std::runtime_error &error) {
            const auto expected = mode == 0   ? "primary action failure"
                                  : mode == 3 ? "primary start failure"
                                              : "first cleanup failure";
            expectedFailure = mode != 1 && mode != 4 && std::string(error.what()) == expected;
        }
        expect_true(expectedFailure && fixture.heroController->ends == 1 && probe(enemy)->ends == (mode == 3 ? 0 : 1),
                    "quarantine must preserve the primary failure and end each actually started controller once");
        expect_true(work.quest->captures == 0 && work.graph->visits == 0 && !fixture.map->tryBeginSaveSnapshot() &&
                        !fixture.game->getMap()->tryBeginSaveSnapshot() && !fixture.map->tryBeginUnsafeOperation(),
                    "uncaught errors and superseded bindings must quarantine even after successful controller ends");
    }
}

void testEncounterEarlyOutcomesAndOuterOwnerRemainIndependent() {
    Fixture fixture;
    fixture.map->setBoolProperty("guardNativeEncounterSaves", true);
    auto enemy = fixture.actor("earlyAdmissionEnemy");
    fixture.map->setStringProperty("combatHistory", "admission sentinel");
    auto snapshot = fixture.map->tryBeginSaveSnapshot();
    const auto rejected = CFightHandler::fightManyResult(fixture.hero, {enemy});
    expect_true(snapshot && rejected.outcome == CFightOutcome::Invalid && fixture.heroController->starts == 0 &&
                    probe(enemy)->starts == 0 &&
                    fixture.map->getStringProperty("combatHistory") == "admission sentinel",
                "snapshot rejection must precede even combat-history mutation and every controller start");
    snapshot.reset();
    expect_true(CFightHandler::fightManyResult(fixture.hero, {}).outcome == CFightOutcome::Invalid &&
                    fixture.map->tryBeginSaveSnapshot().has_value(),
                "an empty-opponent normal early result must settle its empty cleanup ownership");
    fixture.hero->setFightController(nullptr);
    expect_true(CFightHandler::fightManyResult(fixture.hero, {enemy}).outcome == CFightOutcome::Invalid &&
                    fixture.map->tryBeginSaveSnapshot().has_value(),
                "a missing-controller normal early result must release admission without quarantining");
    fixture.hero->setFightController(fixture.heroController);
    auto outer = fixture.map->tryBeginUnsafeOperation();
    fixture.heroController->cancelled = true;
    const auto cancelled = CFightHandler::fightManyResult(fixture.hero, {enemy});
    expect_true(outer && cancelled.outcome == CFightOutcome::Cancelled && !fixture.map->tryBeginSaveSnapshot(),
                "normal native cleanup must not release the independent outer receipt owner");
    if (outer) {
        outer->finish();
    }
    expect_true(fixture.map->tryBeginSaveSnapshot().has_value(),
                "explicit outer settlement must release the final independent hold");
}

void testNaturalMovementEncounterOwnsAdmission() {
    Fixture fixture;
    fixture.map->setBoolProperty("guardNativeEncounterSaves", true);
    fixture.hero->setNpc(false);
    fixture.hero->getBaseStats()->setAgility(30);
    auto enemy = fixture.actor("naturalAdmissionEnemy", false, 1);
    enemy->setNpc(false);
    enemy->setCanStep(true);
    auto ally = fixture.actor("naturalAdmissionAlly", true, 0, 1);
    ally->setCanStep(true);
    fixture.enable("naturalAdmissionAlly");
    for (const int x : {0, 1}) {
        auto tile = std::make_shared<CTile>();
        tile->setGame(fixture.game);
        tile->setCanStep(true);
        fixture.map->addTile(tile, x, 0, 0);
    }
    EncounterAdmissionWork work(fixture);
    fixture.heroController->action = [&](auto, auto) {
        work.attempt();
        fixture.heroController->cancelled = true;
    };
    fixture.hero->moveTo(1, 0, 0);
    expect_true(fixture.heroController->actions == 1 && work.attempts == 1 && work.quest->captures == 0 &&
                    work.graph->visits == 0 && fixture.heroController->ends == 1 && probe(enemy)->ends == 1 &&
                    probe(ally)->ends == 1,
                "actual native movement collision must own encounter admission without a scripted flow begin");
    expect_true(fixture.map->tryBeginSaveSnapshot().has_value(),
                "a normally cancelled movement encounter must release only its native admission hold");
}

void testEncounterEffectSupersessionStopsEveryActorRole() {
    for (int role = 0; role < 3; ++role) {
        Fixture fixture;
        fixture.map->setBoolProperty("guardNativeEncounterSaves", true);
        fixture.hero->getBaseStats()->setAgility(role == 0 ? 30 : 10);
        auto enemy = fixture.actor("supersedingEffectEnemy", false, 1, role == 2 ? 30 : 10);
        auto ally = role == 1 ? fixture.actor("supersedingEffectAlly", true, 0, 30) : nullptr;
        auto affected = role == 0 ? std::shared_ptr<CCreature>(fixture.hero) : role == 1 ? ally : enemy;
        auto replacement = std::make_shared<CMap>();
        replacement->setGame(fixture.game);
        auto effect = std::make_shared<EncounterAdmissionEffect>();
        effect->setGame(fixture.game);
        effect->setTypeId("aRebindingEffect");
        effect->setDuration(2);
        int ticks = 0;
        int stale_ticks = 0;
        int stale_formats = 0;
        effect->callback = [&] {
            ++ticks;
            fixture.game->setMap(replacement);
        };
        affected->addEffect(effect);
        auto stale_effect = std::make_shared<EncounterAdmissionEffect>();
        stale_effect->setGame(fixture.game);
        stale_effect->setTypeId("zMustNotTickEffect");
        stale_effect->setDuration(2);
        stale_effect->callback = [&] { ++stale_ticks; };
        affected->addEffect(stale_effect);
        stale_effect->formatting = [&] { ++stale_formats; };
        const auto result = ally ? CFightHandler::fightManyWithAlliesResult(fixture.hero, {enemy}, {ally})
                                 : CFightHandler::fightManyResult(fixture.hero, {enemy});
        expect_true(result.outcome == CFightOutcome::Cancelled && ticks == 1 && stale_ticks == 0 &&
                        stale_formats == 0 && affected->isAlive() && fixture.heroController->actions == 0 &&
                        probe(enemy)->actions == 0 && (!ally || probe(ally)->actions == 0),
                    "an alive actor's superseding effect must stop before the next effect or any native action");
        expect_true(fixture.heroController->ends == 1 && probe(enemy)->ends == 1 && (!ally || probe(ally)->ends == 1) &&
                        !fixture.map->tryBeginSaveSnapshot() && !replacement->tryBeginSaveSnapshot(),
                    "effect supersession must clean every entered controller once and quarantine both bindings");
    }
}

class EncounterExpiredFormattingEffect : public CEffect {
  public:
    std::function<void()> formatting;
    std::string to_string() override {
        if (formatting) {
            formatting();
        }
        return CEffect::to_string();
    }
};

void testExpiredEffectFormattingSupersessionDoesNotRemoveEffect() {
    Fixture fixture;
    fixture.map->setBoolProperty("guardNativeEncounterSaves", true);
    auto enemy = fixture.actor("expiredEffectSupersessionEnemy");
    auto replacement = std::make_shared<CMap>();
    replacement->setGame(fixture.game);
    auto expired = std::make_shared<EncounterExpiredFormattingEffect>();
    expired->setGame(fixture.game);
    expired->setDuration(0);
    fixture.hero->addEffect(expired);
    int formatting_callbacks = 0;
    expired->formatting = [&] {
        if (++formatting_callbacks == 1) {
            fixture.game->setMap(replacement);
        }
    };
    const auto result = CFightHandler::fightManyResult(fixture.hero, {enemy});
    expect_true(result.outcome == CFightOutcome::Cancelled && formatting_callbacks == 1 &&
                    fixture.hero->getEffects().count(expired) == 1 && fixture.heroController->actions == 0 &&
                    probe(enemy)->actions == 0,
                "expired effect formatting that replaces the map must stop before stale removal or native action");
    expect_true(fixture.heroController->ends == 1 && probe(enemy)->ends == 1 && !fixture.map->tryBeginSaveSnapshot() &&
                    !replacement->tryBeginSaveSnapshot(),
                "expiration supersession must clean entered controllers once and quarantine the changed binding");
}

class EncounterSetupReplacingController : public ProbeController {
  public:
    int setups = 0;
    std::function<void()> setup;
    void setOpponents(std::shared_ptr<CCreature>, const std::vector<std::shared_ptr<CCreature>> &) override {
        ++setups;
        setup();
    }
};

void testEncounterControllerSetupSupersessionDoesNotEnterAnotherStart() {
    for (int role = 0; role < 3; ++role) {
        Fixture fixture;
        fixture.map->setBoolProperty("guardNativeEncounterSaves", true);
        auto enemy = fixture.actor("setupSupersessionEnemy");
        auto ally = fixture.actor("setupSupersessionAlly", true);
        auto replacing = std::make_shared<EncounterSetupReplacingController>();
        auto replacement = std::make_shared<CMap>();
        replacement->setGame(fixture.game);
        const auto supersede = [&] { fixture.game->setMap(replacement); };
        replacing->setup = supersede;
        if (role == 0) {
            fixture.heroController = replacing;
            fixture.hero->setFightController(replacing);
        } else if (role == 1) {
            ally->setFightController(replacing);
        } else {
            probe(enemy)->starting = supersede;
        }
        const auto result = CFightHandler::fightManyWithAlliesResult(fixture.hero, {enemy}, {ally});
        expect_true(result.outcome == CFightOutcome::Cancelled && fixture.heroController->actions == 0 &&
                        probe(enemy)->actions == 0 && probe(ally)->actions == 0,
                    "controller setup/start supersession must stop before another stale start or action");
        expect_true(
            fixture.heroController->starts == (role == 0 ? 0 : 1) &&
                fixture.heroController->ends == (role == 0 ? 0 : 1) && probe(enemy)->starts == (role == 0 ? 0 : 1) &&
                probe(enemy)->ends == (role == 0 ? 0 : 1) && probe(ally)->starts == 0 && probe(ally)->ends == 0 &&
                (role == 2 || replacing->setups == 1) && !fixture.map->tryBeginSaveSnapshot() &&
                !replacement->tryBeginSaveSnapshot(),
            "setters whose start was never entered own no end; already entered controllers end once under quarantine");
    }
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
    testCombatCleanupExceptionsEndEveryControllerOnce();
    testCombatCleanupPreservesPrimaryFailureAndCancellation();
    testCombatOwnsPartialControllerStartsAndPreservesTheirFailure();
    testRejectedCombatAdmissionDoesNotStartOrEndControllers();
    testDirectEncounterSaveAdmissionAndLegacyDefault();
    testEncounterAdmissionSpansEffectsLootAndRemoval();
    testEncounterAdmissionQuarantinesPrimaryCleanupAndBindingFailures();
    testEncounterEarlyOutcomesAndOuterOwnerRemainIndependent();
    testNaturalMovementEncounterOwnsAdmission();
    testEncounterEffectSupersessionStopsEveryActorRole();
    testExpiredEffectFormattingSupersessionDoesNotRemoveEffect();
    testEncounterControllerSetupSupersessionDoesNotEnterAnotherStart();
    return finish_tests();
}
