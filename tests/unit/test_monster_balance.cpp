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

#include "core/CController.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CJson.h"
#include "core/CLoader.h"
#include "core/CMap.h"
#include "core/CNavigation.h"
#include "core/CNavigationSearch.h"
#include "core/CProvider.h"
#include "core/CPythonOverrides.h"
#include "core/CSaveFormat.h"
#include "core/CSerialization.h"
#include "core/CStats.h"
#include "handler/CFightHandler.h"
#include "object/CCreature.h"
#include "object/CCreatureClass.h"
#include "object/CEffect.h"
#include "object/CEvent.h"
#include "object/CInteraction.h"
#include "object/CItem.h"
#include "object/CPlayer.h"
#include "object/CTile.h"
#include "test_harness.h"

#include <pybind11/embed.h>
#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <memory>
#include <stdexcept>
#include <tuple>
#include <type_traits>
#include <vector>

extern "C" PyObject *PyInit__game();

namespace {
void createOpenBalanceMap(const std::shared_ptr<CGame> &game) {
    auto map = std::make_shared<CMap>();
    map->setGame(game);
    game->setMap(map);
    map->setXBounds({{0, 2}});
    map->setYBounds({{0, 2}});
    for (int x = 0; x < 3; ++x) {
        for (int y = 0; y < 3; ++y) {
            auto tile = game->createObject<CTile>("GrassTile");
            map->addTile(tile, x, y, 0);
        }
    }
}

struct RitualTurnState {
    bool used;
    int hp, hpMax, mana, targetHp, targetMana, targetNormalResist, targetShadowResist, targetArmor, targetBlock;
};

struct RitualControlRecord {
    RitualTurnState before, after;
};

RitualTurnState observeRitualTurn(const std::shared_ptr<CCreature> &actor, const std::shared_ptr<CCreature> &target) {
    const auto targetStats = target->getStats();
    return {actor->getBoolProperty("enemyRoleUsed"),
            actor->getHp(),
            actor->getHpMax(),
            actor->getMana(),
            target->getHp(),
            target->getMana(),
            targetStats->getNormalResist(),
            targetStats->getShadowResist(),
            targetStats->getArmor(),
            targetStats->getBlock()};
}

struct RoleBalanceSample {
    bool won;
    int healthSpent;
    int manaSpent;
    int itemsSpent;
    double setupMilliseconds;
    double fightMilliseconds;
    double cleanupMilliseconds;
    std::vector<RitualControlRecord> ritualTurns;
};

class PlayerResourceObserver {
  public:
    explicit PlayerResourceObserver(const std::shared_ptr<CPlayer> &player)
        : player(player), previousHp(std::max(0, player->getHp())), previousMana(player->getMana()),
          previousItems(player->getItems()) {}

    void observe() {
        // Controller boundaries cannot split opposing resource changes inside one callback.
        const auto currentPlayer = player.lock();
        if (!currentPlayer) {
            return;
        }
        const int hp = std::max(0, currentPlayer->getHp());
        const int mana = currentPlayer->getMana();
        const auto items = currentPlayer->getItems();
        healthSpent += std::max(0, previousHp - hp);
        manaSpent += std::max(0, previousMana - mana);
        for (const auto &item : previousItems) {
            itemsSpent += items.contains(item) ? 0 : 1;
        }
        previousHp = hp;
        previousMana = mana;
        previousItems = items;
    }

    int healthSpent = 0;
    int manaSpent = 0;
    int itemsSpent = 0;

  private:
    std::weak_ptr<CPlayer> player;
    int previousHp;
    int previousMana;
    std::set<std::shared_ptr<CItem>> previousItems;
};

class ObservedFightController : public CFightController {
  public:
    ObservedFightController(std::shared_ptr<CFightController> delegate,
                            std::shared_ptr<PlayerResourceObserver> observer,
                            std::shared_ptr<std::vector<RitualControlRecord>> ritualTurns = {})
        : delegate(std::move(delegate)), observer(std::move(observer)), ritualTurns(std::move(ritualTurns)) {}

    bool control(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) override {
        observer->observe();
        const auto before = ritualTurns ? observeRitualTurn(me, opponent) : RitualTurnState{};
        const bool result = delegate->control(me, opponent);
        if (ritualTurns) {
            ritualTurns->push_back({before, observeRitualTurn(me, opponent)});
        }
        observer->observe();
        return result;
    }

    void start(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) override {
        observer->observe();
        delegate->start(me, opponent);
        observer->observe();
    }

    void end(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) override {
        observer->observe();
        delegate->end(me, opponent);
        observer->observe();
    }

    bool isCancelled(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) override {
        observer->observe();
        const bool result = delegate->isCancelled(me, opponent);
        observer->observe();
        return result;
    }

    void setOpponents(std::shared_ptr<CCreature> me,
                      const std::vector<std::shared_ptr<CCreature>> &opponents) override {
        observer->observe();
        delegate->setOpponents(me, opponents);
        observer->observe();
    }

    std::shared_ptr<CCreature> selectOpponent(std::shared_ptr<CCreature> me,
                                              const std::vector<std::shared_ptr<CCreature>> &opponents,
                                              std::shared_ptr<CCreature> opponent) override {
        observer->observe();
        const auto result = delegate->selectOpponent(me, opponents, opponent);
        observer->observe();
        return result;
    }

  private:
    std::shared_ptr<CFightController> delegate;
    std::shared_ptr<PlayerResourceObserver> observer;
    std::shared_ptr<std::vector<RitualControlRecord>> ritualTurns;
};

class ObserverDelegateProbe : public CFightController {
  public:
    void start(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature>) override {
        ++starts;
        me->setMana(me->getMana() - 1);
    }

    bool control(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature>) override {
        ++controls;
        me->setHp(me->getHp() - 4);
        return true;
    }

    void end(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature>) override {
        ++ends;
        me->heal(0);
    }

    bool isCancelled(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override {
        ++cancellations;
        return false;
    }

    void setOpponents(std::shared_ptr<CCreature>, const std::vector<std::shared_ptr<CCreature>> &) override {
        ++opponentUpdates;
    }

    std::shared_ptr<CCreature> selectOpponent(std::shared_ptr<CCreature>,
                                              const std::vector<std::shared_ptr<CCreature>> &,
                                              std::shared_ptr<CCreature> opponent) override {
        ++selections;
        return opponent;
    }

    int starts = 0, controls = 0, ends = 0, cancellations = 0, opponentUpdates = 0, selections = 0;
};

void testObserverRetainsDamageConsumptionAndForwardsOrdinaryControllerCalls() {
    auto game = CGameLoader::loadGame();
    auto player = game->createObject<CPlayer>("Warrior");
    player->setLevel(3);
    player->heal(0);
    player->addMana(0);
    const int fullHp = player->getHp();
    const int fullMana = player->getMana();
    auto consumedItem = game->createObject<CItem>("FullLifePotion");
    player->addItem(consumedItem);
    auto observer = std::make_shared<PlayerResourceObserver>(player);
    player->setHp(fullHp - 20);
    player->setMana(fullMana - 3);
    observer->observe();
    player->heal(0);
    player->addMana(0);
    player->removeItem(consumedItem);
    observer->observe();
    player->setHp(fullHp - 7);
    player->setMana(fullMana - 2);
    player->addItem(game->createObject<CItem>("FullManaPotion"));
    observer->observe();
    expect_true(observer->healthSpent == 27 && observer->manaSpent == 5 && observer->itemsSpent == 1,
                "healing, mana recovery and replacement loot must not erase prior expenditure");

    auto delegate = std::make_shared<ObserverDelegateProbe>();
    ObservedFightController controller(delegate, observer);
    auto enemy = game->createObject<CCreature>("OctoBogz");
    controller.start(player, enemy);
    controller.setOpponents(player, {enemy});
    expect_true(controller.selectOpponent(player, {enemy}, enemy) == enemy,
                "observer must preserve the configured controller's selected opponent");
    expect_true(controller.control(player, enemy), "observer must preserve the configured action result");
    controller.end(player, enemy);
    player->setHp(fullHp - 5);
    expect_true(!controller.isCancelled(player, enemy), "observer must preserve cancellation decisions");
    expect_true(observer->healthSpent == 36 && observer->manaSpent == 6 && observer->itemsSpent == 1,
                "controller observations must count pending effect damage without undoing healing");
    expect_true(delegate->starts == 1 && delegate->controls == 1 && delegate->ends == 1 &&
                    delegate->cancellations == 1 && delegate->opponentUpdates == 1 && delegate->selections == 1,
                "observer must forward every lifecycle and selection call exactly once");
}

RoleBalanceSample runRoleBalanceFight(const std::shared_ptr<CGame> &game, const std::string &playerType,
                                      const std::string &monsterType, unsigned seed, bool rolesEnabled) {
    const auto setupStarted = std::chrono::steady_clock::now();
    auto map = game->getMap();
    auto player = game->createObject<CPlayer>(playerType);
    const auto ordinaryController = player->getFightController();
    player->setLevel(3);
    map->attachPlayer(player, Coords(0, 0, 0));
    player->setFightController(ordinaryController);
    player->setHp(player->getHpMax());
    player->setMana(player->getManaMax());
    auto enemy = game->createObject<CCreature>(monsterType);
    enemy->setName("balanceEnemy");
    enemy->setLevel(2);
    enemy->setPosX(1);
    enemy->setPosY(0);
    map->addObject(enemy);
    enemy->setHp(enemy->getHpMax());
    enemy->setMana(enemy->getManaMax());
    enemy->setBoolProperty("enemyRoleUsed", !rolesEnabled);
    const auto actions = enemy->getInteractions();
    expect_true(std::ranges::any_of(actions, [](const auto &action) { return action->getTypeId() == "Attack"; }),
                "balance fixture must load the real Attack interaction");
    expect_true(
        std::ranges::any_of(actions, [](const auto &action) { return action->getBoolProperty("enemySignature"); }),
        "balance fixture must load its configured Python role signature");
    auto observer = std::make_shared<PlayerResourceObserver>(player);
    auto ritualTurns = (monsterType == "Cultist" || monsterType == "CultLeader")
                           ? std::make_shared<std::vector<RitualControlRecord>>()
                           : nullptr;
    player->setFightController(std::make_shared<ObservedFightController>(ordinaryController, observer));
    enemy->setFightController(
        std::make_shared<ObservedFightController>(enemy->getFightController(), observer, ritualTurns));
    vstd::rng().seed(seed);
    std::srand(seed);
    const auto fightStarted = std::chrono::steady_clock::now();
    const auto result = CFightHandler::fightManyResult(player, {enemy});
    observer->observe();
    const auto cleanupStarted = std::chrono::steady_clock::now();
    RoleBalanceSample sample{
        result.attackerSucceeded(), observer->healthSpent, observer->manaSpent, observer->itemsSpent, 0, 0, 0, {}};
    if (ritualTurns) {
        sample.ritualTurns = std::move(*ritualTurns);
    }
    map->detachPlayer();
    if (map->getObjectByName(enemy->getName()) == enemy) {
        map->removeObject(enemy);
    }
    const auto finished = std::chrono::steady_clock::now();
    const auto milliseconds = [](auto elapsed) { return std::chrono::duration<double, std::milli>(elapsed).count(); };
    sample.setupMilliseconds = milliseconds(fightStarted - setupStarted);
    sample.fightMilliseconds = milliseconds(cleanupStarted - fightStarted);
    sample.cleanupMilliseconds = milliseconds(finished - cleanupStarted);
    return sample;
}

void printRitualTrace(const RoleBalanceSample &sample, const std::string &mode, const std::string &playerType,
                      const std::string &monsterType, unsigned seed, bool allTurns) {
    for (std::size_t i = 0; i < sample.ritualTurns.size(); ++i) {
        const auto &record = sample.ritualTurns[i];
        if (!allTurns && (record.before.used || !record.after.used)) {
            continue;
        }
        const auto &before = record.before;
        const auto &after = record.after;
        std::cerr << "ritual turn " << playerType << '/' << monsterType << " seed " << seed << ' ' << mode
                  << " control " << i + 1 << " used " << before.used << " -> " << after.used << " actor hp "
                  << before.hp << '/' << before.hpMax << " -> " << after.hp << '/' << after.hpMax << " mana "
                  << before.mana << " -> " << after.mana << " target hp " << before.targetHp << " -> " << after.targetHp
                  << " mana " << before.targetMana << " -> " << after.targetMana << " normal/shadow resist "
                  << before.targetNormalResist << '/' << before.targetShadowResist << " -> " << after.targetNormalResist
                  << '/' << after.targetShadowResist << " armor/block " << before.targetArmor << '/'
                  << before.targetBlock << " -> " << after.targetArmor << '/' << after.targetBlock << '\n';
    }
}

void initializeBalancePythonContent() {
    std::cerr << "monster balance: initializing bindings\n";
    auto sys = pybind11::module_::import("sys");
    sys.attr("path").attr("insert")(0, GAME_MONSTER_BALANCE_TEST_RESOURCE_ROOT);
    const auto nativeModule = pybind11::module_::import("_game");
    expect_true(nativeModule.attr("CInteraction").attr("__module__").cast<std::string>() == "_game",
                "embedded native classes must have the production module identity");
    for (const auto &method : {"getEffectiveInteractions", "addEffect"}) {
        expect_true(pybind11::hasattr(nativeModule.attr("CCreature"), method),
                    "role plugins must use the actual bound creature API");
    }
    for (const auto &method : {"setCaster", "setVictim"}) {
        expect_true(pybind11::hasattr(nativeModule.attr("CEffect"), method),
                    "eager role effects require actual bound native actor endpoints");
    }
    pybind11::module_::import("game");
    pybind11::module_::import("json");
    std::cerr << "monster balance: game and json initialized\n";
}

void testInheritedNativeMethodsDoNotBecomePythonOverrides() {
    auto game = CGameLoader::loadGame();
    auto barrier = game->createObject<CInteraction>("Barrier");
    expect_true(CPythonOverrides::find_override(barrier.get(), "performAction").is_none(),
                "a Python interaction inheriting native performAction must not recurse through an override");
    expect_true(!CPythonOverrides::find_override(barrier.get(), "configureEffect").is_none(),
                "the harness must still recognize an authored Python configureEffect override");
    auto effect = game->createObject<CEffect>("BarrierEffect");
    expect_true(CPythonOverrides::find_override(effect.get(), "getCaster").is_none(),
                "a Python effect must inherit native methods without treating them as overrides");
    auto player = game->createObject<CPlayer>("Sorcerer");
    player->heal(0);
    player->addMana(0);
    barrier->onAction(player, player);
    expect_true(!player->getEffects().empty(), "inherited native performAction must return and apply the real barrier");
}

void testRolePacketKeepsRandomStreamsAndConfiguredAttackWeaponCallbacks(bool huntPulse = false, bool cultistHex = false,
                                                                        bool huntCharge = false,
                                                                        bool equalWards = false, int resolvedHit = 0) {
    auto game = CGameLoader::loadGame();
    createOpenBalanceMap(game);
    auto expectedNativeRng = vstd::rng();
    int expectedNextBlockRoll = 0;
    int expectedWeaponCalls = 0;
    int expectedPlayerHp = 0;
    bool observedWeaponProc = false;
    for (unsigned seed = 100; seed < 111; ++seed) {
        for (bool enabled : {false, true}) {
            auto player = game->createObject<CPlayer>("Warrior");
            player->setLevel(3);
            if (resolvedHit > 0) {
                auto baseStats = player->getBaseStats();
                baseStats->setNormalResist(95);
                baseStats->setShadowResist(0);
                const auto stats = player->getStats();
                expect_true(
                    stats->getNormalResist() == 95 && stats->getShadowResist() == 0,
                    "the raw-hit boundary must satisfy the same controlled unequal-ward condition in both modes");
            }
            if (equalWards) {
                const auto originalStats = player->getStats();
                auto baseStats = player->getBaseStats();
                baseStats->setShadowResist(baseStats->getShadowResist() + originalStats->getNormalResist() -
                                           originalStats->getShadowResist());
                baseStats->setArmor(17);
                baseStats->setBlock(25);
                const auto stats = player->getStats();
                expect_true(stats->getNormalResist() == stats->getShadowResist() && stats->getArmor() > 0 &&
                                stats->getBlock() > 0,
                            "equal-ward packet contract must exercise existing armor and blocking");
            }
            game->getMap()->attachPlayer(player, Coords(0, 0, 0));
            player->heal(0);
            auto actor = game->createObject<CCreature>((huntPulse || huntCharge) ? "OctoBogz"
                                                       : cultistHex              ? "Cultist"
                                                                                 : "PritzMage");
            actor->setName("roleContractActor");
            actor->setLevel((huntPulse || huntCharge) ? 1 : 2);
            actor->setPosX(1);
            game->getMap()->addObject(actor);
            actor->setMana(cultistHex ? 5 : 0);
            actor->setBoolProperty("enemyRoleUsed", !enabled);
            if (huntPulse || huntCharge) {
                auto director = game->createObject<CEvent>("OctobogzHuntDirector");
                pybind11::cast(director).attr("configureActor")(actor, "brood");
                actor->setStringProperty("octobogzCombatPhase",
                                         enabled ? (huntCharge ? "predator" : "charged") : "spent");
                actor->setBoolProperty("octobogzPulseUsed", !enabled);
                actor->setMana(5);
            }
            auto weapon = game->createObject<CWeapon>("Staff");
            actor->setEquipped({{"0", weapon}});
            actor->heal(0);
            if (resolvedHit > 0) {
                const auto originalStats = actor->getStats();
                auto baseStats = actor->getBaseStats();
                baseStats->setDmgMin(baseStats->getDmgMin() + resolvedHit - originalStats->getDamage() -
                                     originalStats->getDmgMin());
                baseStats->setDmgMax(baseStats->getDmgMax() + resolvedHit - originalStats->getDamage() -
                                     originalStats->getDmgMax());
                baseStats->setHit(100);
                baseStats->setCrit(baseStats->getCrit() - originalStats->getCrit());
                const auto controlledStats = actor->getStats();
                expect_true(controlledStats->getDmgMin() + controlledStats->getDamage() == resolvedHit &&
                                controlledStats->getDmgMax() + controlledStats->getDamage() == resolvedHit &&
                                controlledStats->getCrit() == 0 && controlledStats->getHit() >= 100,
                            "the native boundary fixture must resolve the same exact noncritical hit for both modes");
            }
            if (cultistHex) {
                actor->setHp(std::max(1, actor->getHpMax() / 4));
            }
            if (huntCharge) {
                actor->setHp(std::max(1, actor->getHpMax() / 4));
            }
            const auto interactions = actor->getInteractions();
            const auto attackIt =
                std::ranges::find_if(interactions, [](const auto &action) { return action->getTypeId() == "Attack"; });
            if (attackIt == interactions.end() || !weapon->getInteraction()) {
                expect_true(false, "role contract fixture must load real Attack and configured Staff interaction");
                return;
            }
            const auto attack = *attackIt;
            const auto signatureIt =
                std::ranges::find_if(interactions, [huntPulse, cultistHex, huntCharge](const auto &action) {
                    return action->getTypeId() == (huntCharge   ? "octobogzCharge"
                                                   : huntPulse  ? "octobogzShadowPulse"
                                                   : cultistHex ? "enemyRitualHex"
                                                                : "enemyArcaneBolt");
                });
            if (signatureIt == interactions.end()) {
                expect_true(false, "paired contract must load its actual configured signature");
                return;
            }
            auto globals = pybind11::dict();
            globals["attack"] = pybind11::cast(attack);
            globals["weaponAction"] = pybind11::cast(weapon->getInteraction());
            globals["signature"] = pybind11::cast(*signatureIt);
            pybind11::exec(R"(
attackType = type(attack)
weaponType = type(weaponAction)
signatureType = type(signature)
originalAttack = attackType.performAction
originalWeaponAction = weaponType.performAction
originalSignature = signatureType.performAction
calls = {'attack': 0, 'weapon': 0, 'error': ''}
def invokeRecorded(kind, method, self, first, second):
    try:
        return method(self, first, second)
    except Exception as error:
        calls['error'] += kind + ': ' + type(error).__name__ + ': ' + str(error) + '\n'
        raise
def countedAttack(self, first, second):
    calls['attack'] += 1
    return invokeRecorded('Attack', originalAttack, self, first, second)
def countedWeaponAction(self, first, second):
    calls['weapon'] += 1
    return invokeRecorded('weapon', originalWeaponAction, self, first, second)
def recordedSignature(self, first, second):
    return invokeRecorded('signature', originalSignature, self, first, second)
attackType.performAction = countedAttack
weaponType.performAction = countedWeaponAction
signatureType.performAction = recordedSignature
)",
                           globals);
            const auto recipient = (huntPulse || cultistHex) ? vstd::cast<CCreature>(player) : actor;
            const int beforeResist = (huntPulse || cultistHex) ? recipient->getStats()->getShadowResist()
                                                               : recipient->getStats()->getNormalResist();
            vstd::rng().seed(seed);
            std::srand(seed);
            CMonsterFightController controller;
            const bool acted = controller.control(actor, player);
            const auto afterNativeRng = vstd::rng();
            const int nextBlockRoll = std::rand();
            pybind11::exec(R"(
attackType.performAction = originalAttack
weaponType.performAction = originalWeaponAction
signatureType.performAction = originalSignature
)",
                           globals);
            expect_true(acted, "real configured Attack must execute in the role contract fixture");
            const auto calls = globals["calls"].cast<pybind11::dict>();
            const auto callbackError = calls["error"].cast<std::string>();
            if (!callbackError.empty()) {
                std::cerr << "role callback error seed " << seed << ": " << callbackError;
            }
            expect_true(callbackError.empty(), "real configured callbacks must not raise a Python exception");
            const int weaponCalls = calls["weapon"].cast<int>();
            expect_true(calls["attack"].cast<int>() == 1 && weaponCalls <= 1,
                        "signature and ordinary Attack must retain one attack and at most one configured weapon proc");
            observedWeaponProc |= weaponCalls == 1;
            expect_true(!actor->getBoolProperty("enemyRoleArcaneAttack") &&
                            actor->getStringProperty("enemyRoleDamageChannel").empty() &&
                            actor->getNumericProperty("enemyRoleDamageMinimum") == 0,
                        "the temporary damage hook must be disarmed before a save or subsequent action");
            if (enabled) {
                if (resolvedHit > 0) {
                    expect_true(actor->getNumericProperty("enemyRoleAttackBudget") == resolvedHit && weaponCalls == 1,
                                "the boundary fixture must resolve exactly one real hit and configured weapon proc");
                    const auto packet = actor->getObjectProperty<CDamage>("enemyRoleDamagePacket");
                    expect_true(packet && packet->getNumericProperty("shadow") == (resolvedHit >= 10 ? 1 : 0),
                                "the ritual shadow component must begin at the ten-point resolved-hit boundary");
                    if (resolvedHit < 10) {
                        expect_true(player->getHp() == expectedPlayerHp,
                                    "a nine-point ritual hit must preserve ordinary mitigation and weapon damage");
                    } else if (packet) {
                        expect_true(packet->getNumericProperty("normal") == resolvedHit - 1,
                                    "the ritual packet must retain the complete original raw damage budget");
                    }
                }
                if (equalWards) {
                    expect_true(player->getHp() == expectedPlayerHp && !actor->hasProperty("enemyRoleAttackBudget"),
                                "equal wards must preserve the whole ordinary Attack mitigation and block path");
                }
                expect_true(afterNativeRng == expectedNativeRng && nextBlockRoll == expectedNextBlockRoll,
                            "eager owned role objects must preserve both ordinary Attack random streams");
                expect_true(weaponCalls == expectedWeaponCalls,
                            "the role hook must preserve the configured weapon proc on both hits and misses");
                if (huntCharge) {
                    expect_true(player->getHp() == expectedPlayerHp,
                                "the actual warning Attack must retain exactly the ordinary damage and weapon proc");
                    expect_true(actor->getMana() == 5 && actor->getEffects().empty() && player->getEffects().empty() &&
                                    actor->getStringProperty("octobogzCombatPhase") == "charged" &&
                                    !actor->getBoolProperty("octobogzPulseUsed") &&
                                    !actor->getBoolProperty("enemyRoleUsed"),
                                "a real warning must retain ordinary Attack without mana, effects or brute signature");
                } else {
                    expect_true(signatureIt != interactions.end() &&
                                    !(*signatureIt)->getObjectProperty<CGameObject>("roleEffect"),
                                "consumed eager effects must transfer out of the actor-owned signature slot");
                    const int afterResist = (huntPulse || cultistHex) ? recipient->getStats()->getShadowResist()
                                                                      : recipient->getStats()->getNormalResist();
                    expect_true(afterResist == beforeResist - 1 && recipient->getEffects().size() == 1,
                                "the one-turn signature tradeoff must actually affect combat stats");
                    if (huntPulse) {
                        expect_true(actor->getMana() == 0 && actor->getBoolProperty("octobogzPulseUsed") &&
                                        actor->getBoolProperty("octobogzPulseEffectApplied"),
                                    "an actual pulse must spend exactly five mana and apply its owned effect once");
                        expect_true(!actor->getBoolProperty("enemyRoleUsed"),
                                    "a hunt pulse must remain exclusive of the composed brute class signature");
                    }
                    if (!recipient->getEffects().empty()) {
                        const auto effect = *recipient->getEffects().begin();
                        expect_true(effect->getTimeLeft() == 1 && effect->getCaster() == actor &&
                                        effect->getVictim() == recipient,
                                    "the eagerly owned effect must have a real duration and actor endpoints");
                        effect->apply(recipient);
                        expect_true(effect->getTimeLeft() == 0, "the role effect must expire after one application");
                    }
                }
            } else {
                expectedNativeRng = afterNativeRng;
                expectedNextBlockRoll = nextBlockRoll;
                expectedWeaponCalls = weaponCalls;
                expectedPlayerHp = player->getHp();
                const int afterResist = (huntPulse || cultistHex) ? recipient->getStats()->getShadowResist()
                                                                  : recipient->getStats()->getNormalResist();
                expect_true(recipient->getEffects().empty() && afterResist == beforeResist,
                            "disabled roles must leave ordinary Attack stats unchanged");
                if (huntPulse || huntCharge) {
                    expect_true(actor->getMana() == 5,
                                "disabled hunt phases must preserve all five ordinary baseline mana points");
                }
            }
            game->getMap()->detachPlayer();
            game->getMap()->removeObject(actor);
        }
    }
    expect_true(observedWeaponProc, "paired role contract samples must exercise a real configured weapon proc");
}

class HexTurnProbe : public CFightController {
  public:
    HexTurnProbe(std::vector<std::string> &order, int stopAfter) : order(order), stopAfter(stopAfter) {}

    bool control(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature>) override {
        order.push_back(me->getName());
        shadowResists.push_back(me->getStats()->getShadowResist());
        timesLeft.push_back(me->getEffects().empty() ? -1 : (*me->getEffects().begin())->getTimeLeft());
        return true;
    }

    bool isCancelled(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override {
        return static_cast<int>(shadowResists.size()) >= stopAfter;
    }

    std::vector<int> shadowResists;
    std::vector<int> timesLeft;

  private:
    std::vector<std::string> &order;
    int stopAfter;
};

class HexAttackProbe : public CMonsterFightController {
  public:
    explicit HexAttackProbe(std::vector<std::string> &order) : order(order) {}

    bool control(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) override {
        order.push_back(me->getName());
        const int before = opponent->getHp();
        const bool acted = CMonsterFightController::control(me, opponent);
        damage.push_back(before - opponent->getHp());
        return acted;
    }

    std::vector<int> damage;

  private:
    std::vector<std::string> &order;
};

void testCultistShadowPacketAndExpiryFollowActualFightInitiativeBoundaries(bool huntPulse = false) {
    const auto previousRng = vstd::rng();
    for (bool cultistFirst : {false, true}) {
        for (bool enabled : {false, true}) {
            auto game = CGameLoader::loadGame();
            createOpenBalanceMap(game);
            auto player = game->createObject<CPlayer>("Warrior");
            auto targetStats = std::make_shared<CStats>();
            targetStats->setStamina(100);
            targetStats->setStrength(1);
            targetStats->setNormalResist(95);
            targetStats->setShadowResist(0);
            targetStats->setAgility(cultistFirst ? 0 : 100);
            player->setCreatureClass(nullptr);
            player->setRace(nullptr);
            player->setBaseStats(targetStats);
            player->setLevelStats(std::make_shared<CStats>());
            player->setEquipped({});
            player->setLevel(1);
            game->getMap()->attachPlayer(player, Coords(0, 0, 0));
            player->heal(0);

            auto actor = game->createObject<CCreature>(huntPulse ? "OctoBogz" : "Cultist");
            actor->setName("hexBoundaryActor");
            actor->setRace(nullptr);
            actor->setLevelStats(std::make_shared<CStats>());
            actor->setEquipped({});
            actor->setLevel(1);
            auto attackStats = std::make_shared<CStats>();
            attackStats->setStamina(100);
            attackStats->setDmgMin(21);
            attackStats->setDmgMax(21);
            attackStats->setHit(100);
            attackStats->setCrit(0);
            attackStats->setAgility(cultistFirst ? 100 : 0);
            actor->setBaseStats(attackStats);
            actor->setPosX(1);
            game->getMap()->addObject(actor);
            actor->heal(0);
            const int ritualHealthDivisor = 4;
            actor->setHp(std::max(1, actor->getHpMax() / ritualHealthDivisor));
            actor->setMana(5);
            actor->setBoolProperty("enemyRoleUsed", !enabled);
            if (huntPulse) {
                auto director = game->createObject<CEvent>("OctobogzHuntDirector");
                pybind11::cast(director).attr("configureActor")(actor, "brood");
                actor->setStringProperty("octobogzCombatPhase", enabled ? "charged" : "spent");
                actor->setBoolProperty("octobogzPulseUsed", !enabled);
            }
            std::vector<std::string> order;
            auto targetController = std::make_shared<HexTurnProbe>(order, cultistFirst ? 2 : 3);
            auto cultistController = std::make_shared<HexAttackProbe>(order);
            player->setFightController(targetController);
            actor->setFightController(cultistController);
            vstd::rng().seed(100);
            std::srand(100);
            const auto result = CFightHandler::fightManyResult(player, {actor});
            expect_true(result.outcome == CFightOutcome::Cancelled,
                        "the boundary fixture must stop after observing effect expiry without a defeat");
            expect_true(!order.empty() && order.front() == (cultistFirst ? actor->getName() : player->getName()),
                        "the real fight must execute both controlled initiative orders");
            expect_true(!cultistController->damage.empty() && cultistController->damage.front() == (enabled ? 2 : 1),
                        "a shadow point must cause real extra damage against controlled unequal channel resistance");
            const std::vector<int> expectedResists = !enabled       ? std::vector<int>(cultistFirst ? 2 : 3, 0)
                                                     : cultistFirst ? std::vector<int>{-1, 0}
                                                                    : std::vector<int>{0, -1, 0};
            const std::vector<int> expectedTimes = !enabled       ? std::vector<int>(cultistFirst ? 2 : 3, -1)
                                                   : cultistFirst ? std::vector<int>{0, -1}
                                                                  : std::vector<int>{-1, 0, -1};
            expect_true(targetController->shadowResists == expectedResists &&
                            targetController->timesLeft == expectedTimes,
                        "the one-turn shadow effect must affect one victim turn and expire at its next turn boundary");
            expect_true(player->getEffects().empty() && player->getStats()->getShadowResist() == 0,
                        "actual fight expiry must restore target resistance and remove the linked effect");
            if (huntPulse) {
                expect_true(actor->getMana() == (enabled ? 0 : 5) &&
                                actor->getStringProperty("octobogzCombatPhase") == "spent",
                            "a real pulse must spend exactly five mana once across either initiative order");
                if (enabled) {
                    expect_true(actor->getBoolProperty("octobogzPulseUsed") &&
                                    actor->getBoolProperty("octobogzPulseEffectApplied") &&
                                    !actor->getBoolProperty("enemyRoleUsed"),
                                "the actual shadow phase must apply its effect and remain exclusive of brute");
                }
            }
        }
    }
    vstd::rng() = previousRng;
}

void testMonsterRolesPreserveOrdinaryLoadoutWinsAndResourceBudget(const std::string &selectedClass = {}) {
    const auto previousRng = vstd::rng();
    auto game = CGameLoader::loadGame();
    createOpenBalanceMap(game);
    auto median = [](std::vector<int> values) {
        std::sort(values.begin(), values.end());
        return values[values.size() / 2];
    };
    for (const auto &playerType : {"Warrior", "Sorcerer", "Assasin", "Inquisitor", "Wayfarer"}) {
        if (!selectedClass.empty() && selectedClass != playerType) {
            continue;
        }
        bool classHasMandatoryBaselineWitness = false;
        int completedRows = 0, completedPairedSeeds = 0;
        for (const auto &monsterType :
             {"Gooby", "Pritz", "OctoBogz", "PritzMage", "GoblinThief", "Cultist", "CultLeader"}) {
            std::vector<int> baselineHp, roleHp, baselineMana, roleMana, baselineItems, roleItems;
            int baselineWins = 0;
            double setupMilliseconds = 0, fightMilliseconds = 0, cleanupMilliseconds = 0;
            for (unsigned seed = 100; seed < 111; ++seed) {
                const auto baseline = runRoleBalanceFight(game, playerType, monsterType, seed, false);
                const auto roles = runRoleBalanceFight(game, playerType, monsterType, seed, true);
                printRitualTrace(roles, "roles", playerType, monsterType, seed, false);
                ++completedPairedSeeds;
                baselineWins += baseline.won ? 1 : 0;
                setupMilliseconds += baseline.setupMilliseconds + roles.setupMilliseconds;
                fightMilliseconds += baseline.fightMilliseconds + roles.fightMilliseconds;
                cleanupMilliseconds += baseline.cleanupMilliseconds + roles.cleanupMilliseconds;
                if (baseline.won && !roles.won) {
                    printRitualTrace(baseline, "baseline", playerType, monsterType, seed, true);
                    printRitualTrace(roles, "roles", playerType, monsterType, seed, true);
                    std::cerr << "role victory regression " << playerType << '/' << monsterType << " seed " << seed
                              << " baseline hp/mana/items " << baseline.healthSpent << '/' << baseline.manaSpent << '/'
                              << baseline.itemsSpent << " roles " << roles.healthSpent << '/' << roles.manaSpent << '/'
                              << roles.itemsSpent << '\n';
                }
                expect_true(!baseline.won || roles.won, "monster role must preserve every seeded baseline victory");
                baselineHp.push_back(baseline.healthSpent);
                roleHp.push_back(roles.healthSpent);
                baselineMana.push_back(baseline.manaSpent);
                roleMana.push_back(roles.manaSpent);
                baselineItems.push_back(baseline.itemsSpent);
                roleItems.push_back(roles.itemsSpent);
            }
            const bool representative = std::string(monsterType) == "Gooby" || std::string(monsterType) == "Pritz" ||
                                        std::string(monsterType) == "OctoBogz";
            classHasMandatoryBaselineWitness |= representative && baselineWins > 0 && median(baselineHp) > 0;
            const bool originalAllLosingPair =
                std::string(playerType) == "Sorcerer" && std::string(monsterType) == "CultLeader";
            const bool originalHarmlessMedianPair =
                std::string(playerType) == "Assasin" && std::string(monsterType) == "Pritz";
            if (!originalAllLosingPair) {
                expect_true(baselineWins > 0, "each previously winning authored pair must retain baseline wins");
            }
            const bool originallyRequiredDamage =
                std::string(monsterType) == "Pritz" || std::string(monsterType) == "OctoBogz";
            if (originallyRequiredDamage && !originalHarmlessMedianPair) {
                expect_true(median(baselineHp) > 0,
                            "each previously damaging authored pair must retain baseline damage");
            }
            std::cout << "role balance " << playerType << '/' << monsterType << " hp " << median(baselineHp) << " -> "
                      << median(roleHp) << " mana " << median(baselineMana) << " -> " << median(roleMana) << " items "
                      << median(baselineItems) << " -> " << median(roleItems) << " baseline wins " << baselineWins
                      << "/11 setup/fight/cleanup ms " << setupMilliseconds << '/' << fightMilliseconds << '/'
                      << cleanupMilliseconds << std::endl;
            expect_true(std::abs(median(roleHp) - median(baselineHp)) * 10 <= median(baselineHp),
                        "monster roles must keep median health expenditure within 10 percent of baseline");
            expect_true(std::abs(median(roleMana) - median(baselineMana)) * 10 <= median(baselineMana),
                        "monster roles must keep median mana expenditure within 10 percent of baseline");
            expect_true(std::abs(median(roleItems) - median(baselineItems)) * 10 <= median(baselineItems),
                        "monster roles must keep median item expenditure within 10 percent of baseline");
            ++completedRows;
        }
        expect_true(classHasMandatoryBaselineWitness,
                    "each class must win against a representative authored enemy that also causes baseline damage");
        expect_true(completedRows == 7 && completedPairedSeeds == 77,
                    "each class partition must execute all seven rows and 77 paired seeds");
        std::cout << "role class complete " << playerType << " rows=" << completedRows
                  << " pairedSeeds=" << completedPairedSeeds << " fights=" << completedPairedSeeds * 2 << std::endl;
    }
    vstd::rng() = previousRng;
}

void testActivePlayerNeverUsesMonsterSignature() {
    auto game = CGameLoader::loadGame();
    createOpenBalanceMap(game);
    auto player = game->createObject<CPlayer>("Warrior");
    game->getMap()->attachPlayer(player, Coords(0, 0, 0));
    player->setCreatureClass(game->createObject<CCreatureClass>("bruteClass"));
    player->addAction(game->createObject<CInteraction>("Attack"));
    player->setHp(1);
    player->setMana(0);
    auto enemy = game->createObject<CCreature>("OctoBogz");
    enemy->setName("playerRoleExclusionEnemy");
    enemy->setPosX(1);
    game->getMap()->addObject(enemy);
    expect_true(player->isPlayer(), "role exclusion fixture must use the real canonical player");
    CMonsterFightController controller;
    expect_true(controller.control(player, enemy), "player should retain an ordinary attack");
    expect_true(!player->getBoolProperty("enemyRoleUsed"), "player must never use a monster signature");
}

struct HuntBalanceSample {
    RoleBalanceSample resources;
    int alphaPulses;
    int broodPulses;
};

HuntBalanceSample runHuntBalanceRoute(const std::shared_ptr<CGame> &game, const std::string &playerType, unsigned seed,
                                      bool stagedHunt) {
    const auto setupStarted = std::chrono::steady_clock::now();
    auto map = game->getMap();
    auto player = game->createObject<CPlayer>(playerType);
    const auto ordinaryController = player->getFightController();
    player->setLevel(3);
    map->attachPlayer(player, Coords(0, 0, 0));
    player->setFightController(ordinaryController);
    player->heal(0);
    player->addMana(0);
    const auto director = game->createObject<CEvent>("OctobogzHuntDirector");
    std::vector<std::shared_ptr<CCreature>> enemies;
    for (const auto &slot : {"scout", "alpha", "brood"}) {
        auto enemy = game->createObject<CCreature>("OctoBogz");
        enemy->setName("routeOctobogz" + std::string(slot));
        // The authored map creates fresh OctoBogz actors, which enter at level one.
        enemy->setLevel(1);
        enemy->setPosX(1);
        map->addObject(enemy);
        enemy->heal(0);
        enemy->addMana(0);
        if (stagedHunt) {
            pybind11::cast(director).attr("configureActor")(enemy, slot);
        } else {
            enemy->setBoolProperty("enemyRoleUsed", true);
        }
        enemies.push_back(enemy);
    }
    auto observer = std::make_shared<PlayerResourceObserver>(player);
    player->setFightController(std::make_shared<ObservedFightController>(ordinaryController, observer));
    for (const auto &enemy : enemies) {
        enemy->setFightController(std::make_shared<ObservedFightController>(enemy->getFightController(), observer));
    }
    // The original cave configured three OctoBogz. Compare that fixed footprint,
    // without the old prop's unbounded onTurn flood, with ordinary Lv3 players and authored Lv1 enemies.
    vstd::rng().seed(seed);
    std::srand(seed);
    const auto tracePlayer = [&](const std::string &stage) {
        std::cout << "hunt route trace " << playerType << " seed " << seed << " staged " << stagedHunt << " stage "
                  << stage << " player level/exp/hp/mp " << player->getLevel() << '/'
                  << player->getNumericProperty("exp") << '/' << player->getHp() << '/' << player->getMana()
                  << " max hp/mp " << player->getHpMax() << '/' << player->getManaMax() << " equipment";
        for (const auto &[slot, item] : player->getEquipped()) {
            std::cout << ' ' << slot << ':' << (item ? item->getTypeId() : "none");
        }
        std::cout << " inventory";
        for (const auto &item : player->getItems()) {
            std::cout << ' ' << item->getTypeId();
        }
        std::cout << " spent hp/mp/items " << observer->healthSpent << '/' << observer->manaSpent << '/'
                  << observer->itemsSpent << std::endl;
    };
    tracePlayer("start");
    const auto fightStarted = std::chrono::steady_clock::now();
    bool won = true;
    for (const auto &enemy : enemies) {
        if (!player->isAlive()) {
            won = false;
            break;
        }
        const auto result = CFightHandler::fightManyResult(player, {enemy});
        observer->observe();
        tracePlayer(enemy->getName());
        std::cout << "hunt encounter trace " << playerType << " seed " << seed << " staged " << stagedHunt << " enemy "
                  << enemy->getName() << " level/hp/mp " << enemy->getLevel() << '/' << enemy->getHp() << '/'
                  << enemy->getMana() << " outcome " << static_cast<int>(result.outcome) << " rounds " << result.rounds
                  << " phase " << enemy->getStringProperty("octobogzCombatPhase") << " pulse/effect "
                  << enemy->getBoolProperty("octobogzPulseUsed") << '/'
                  << enemy->getBoolProperty("octobogzPulseEffectApplied") << std::endl;
        if (!result.attackerSucceeded()) {
            won = false;
            break;
        }
    }
    observer->observe();
    const auto cleanupStarted = std::chrono::steady_clock::now();
    HuntBalanceSample sample{
        {won, observer->healthSpent, observer->manaSpent, observer->itemsSpent, 0, 0, 0},
        enemies[1]->getBoolProperty("octobogzPulseUsed") && enemies[1]->getBoolProperty("octobogzPulseEffectApplied")
            ? 1
            : 0,
        enemies[2]->getBoolProperty("octobogzPulseUsed") && enemies[2]->getBoolProperty("octobogzPulseEffectApplied")
            ? 1
            : 0};
    map->detachPlayer();
    for (const auto &enemy : enemies) {
        if (map->getObjectByName(enemy->getName()) == enemy) {
            map->removeObject(enemy);
        }
    }
    const auto finished = std::chrono::steady_clock::now();
    const auto milliseconds = [](auto elapsed) { return std::chrono::duration<double, std::milli>(elapsed).count(); };
    sample.resources.setupMilliseconds = milliseconds(fightStarted - setupStarted);
    sample.resources.fightMilliseconds = milliseconds(cleanupStarted - fightStarted);
    sample.resources.cleanupMilliseconds = milliseconds(finished - cleanupStarted);
    return sample;
}

void testStagedHuntPreservesOriginalThreeActorRouteWinsAndResourceBudget() {
    const auto previousRng = vstd::rng();
    auto game = CGameLoader::loadGame();
    createOpenBalanceMap(game);
    const auto median = [](std::vector<int> values) {
        std::sort(values.begin(), values.end());
        return values[values.size() / 2];
    };
    int allAlphaPulses = 0, allBroodPulses = 0;
    for (const auto &playerType : {"Warrior", "Sorcerer", "Assasin", "Inquisitor", "Wayfarer"}) {
        std::vector<int> baselineHp, huntHp, baselineMana, huntMana, baselineItems, huntItems;
        int baselineWins = 0, alphaPulses = 0, broodPulses = 0;
        double setupMilliseconds = 0, fightMilliseconds = 0, cleanupMilliseconds = 0;
        for (unsigned seed = 100; seed < 111; ++seed) {
            const auto baseline = runHuntBalanceRoute(game, playerType, seed, false).resources;
            const auto hunt = runHuntBalanceRoute(game, playerType, seed, true);
            baselineWins += baseline.won ? 1 : 0;
            alphaPulses += hunt.alphaPulses;
            broodPulses += hunt.broodPulses;
            if (baseline.won && !hunt.resources.won) {
                std::cerr << "hunt victory regression " << playerType << " seed " << seed << " baseline hp/mana/items "
                          << baseline.healthSpent << '/' << baseline.manaSpent << '/' << baseline.itemsSpent << " hunt "
                          << hunt.resources.healthSpent << '/' << hunt.resources.manaSpent << '/'
                          << hunt.resources.itemsSpent << '\n';
            }
            expect_true(!baseline.won || hunt.resources.won,
                        "staged hunt must preserve every seeded baseline route victory");
            setupMilliseconds += baseline.setupMilliseconds + hunt.resources.setupMilliseconds;
            fightMilliseconds += baseline.fightMilliseconds + hunt.resources.fightMilliseconds;
            cleanupMilliseconds += baseline.cleanupMilliseconds + hunt.resources.cleanupMilliseconds;
            baselineHp.push_back(baseline.healthSpent);
            huntHp.push_back(hunt.resources.healthSpent);
            baselineMana.push_back(baseline.manaSpent);
            huntMana.push_back(hunt.resources.manaSpent);
            baselineItems.push_back(baseline.itemsSpent);
            huntItems.push_back(hunt.resources.itemsSpent);
        }
        const bool originallyWinningClass =
            std::string(playerType) == "Assasin" || std::string(playerType) == "Inquisitor";
        if (originallyWinningClass) {
            expect_true(baselineWins > 0,
                        "each originally winning no-rest hunt class must retain real three-actor victories");
        }
        expect_true(median(baselineHp) > 0, "three-actor route baseline must cause nonzero incoming damage");
        std::cout << "hunt route balance " << playerType << " hp " << median(baselineHp) << " -> " << median(huntHp)
                  << " mana " << median(baselineMana) << " -> " << median(huntMana) << " items "
                  << median(baselineItems) << " -> " << median(huntItems) << " baseline wins " << baselineWins
                  << "/11 alpha/brood pulses " << alphaPulses << '/' << broodPulses << " setup/fight/cleanup ms "
                  << setupMilliseconds << '/' << fightMilliseconds << '/' << cleanupMilliseconds << std::endl;
        expect_true(std::abs(median(huntHp) - median(baselineHp)) * 10 <= median(baselineHp),
                    "hunt route must keep median health expenditure within 10 percent of baseline");
        expect_true(std::abs(median(huntMana) - median(baselineMana)) * 10 <= median(baselineMana),
                    "hunt route must keep median mana expenditure within 10 percent of baseline");
        expect_true(std::abs(median(huntItems) - median(baselineItems)) * 10 <= median(baselineItems),
                    "hunt route must keep median item expenditure within 10 percent of baseline");
        allAlphaPulses += alphaPulses;
        allBroodPulses += broodPulses;
    }
    expect_true(allAlphaPulses > 0 && allBroodPulses > 0,
                "route comparison must exercise actual wounded Alpha and shadow brood pulses");
    vstd::rng() = previousRng;
}
void requireHuntDecision(bool condition, const char *message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

json huntItemIdentity(const std::shared_ptr<CItem> &item) {
    return item ? json{{"name", item->getName()}, {"typeId", item->getTypeId()}, {"power", item->getPower()}}
                : json(nullptr);
}

json huntPlayerSnapshot(const std::shared_ptr<CPlayer> &player) {
    const auto serialized = object_serialize(player);
    json equipment = json::object();
    for (const auto &[slot, item] : player->getEquipped()) {
        equipment[slot] = huntItemIdentity(item);
    }
    auto items = player->getItems();
    std::vector<std::shared_ptr<CItem>> orderedItems(items.begin(), items.end());
    std::sort(orderedItems.begin(), orderedItems.end(), [](const auto &left, const auto &right) {
        return std::tuple(left->getName(), left->getTypeId(), left->getPower()) <
               std::tuple(right->getName(), right->getTypeId(), right->getPower());
    });
    json inventory = json::array();
    for (const auto &item : orderedItems) {
        inventory[inventory.size()] = huntItemIdentity(item);
    }
    const auto coords = player->getCoords();
    return {{"name", player->getName()},
            {"typeId", player->getTypeId()},
            {"classId", player->getPlayerClassId()},
            {"raceId", player->getRaceId()},
            {"archetypeRaceId", player->getArchetypeRaceId()},
            {"archetypeClassId", player->getArchetypeClassId()},
            {"level", player->getLevel()},
            {"exp", player->getNumericProperty("exp")},
            {"hp", player->getHp()},
            {"mana", player->getMana()},
            {"gold", player->getGold()},
            {"hpMax", player->getHpMax()},
            {"manaMax", player->getManaMax()},
            {"equipment", equipment},
            {"inventory", inventory},
            {"effects", serialized->at("properties").at("effects")},
            {"baseStats", *object_serialize(player->getBaseStats())},
            {"levelStats", *object_serialize(player->getLevelStats())},
            {"coords", {{"x", coords.x}, {"y", coords.y}, {"z", coords.z}}}};
}

struct HuntDecisionActor {
    std::string slot;
    std::shared_ptr<CCreature> actor;
    std::shared_ptr<CFightController> controller;
    int mana;
    std::string phase;
    bool pulse;
    std::set<std::shared_ptr<CItem>> items;
};

class HuntDecisionController : public CFightController {
  public:
    HuntDecisionController(const std::shared_ptr<CPlayer> &player, std::vector<HuntDecisionActor> actors)
        : actors(std::move(actors)), player(player), carriedItems(player->getItems()) {}

    void observe() {
        for (auto &entry : actors) {
            auto actor = entry.actor;
            const int mana = actor->getMana();
            const auto phase = actor->getStringProperty("octobogzCombatPhase");
            const bool pulse = actor->getBoolProperty("octobogzPulseUsed");
            if (!entry.pulse && pulse) {
                auto packet = actor->hasProperty("enemyRoleDamagePacket")
                                  ? actor->getObjectProperty<CDamage>("enemyRoleDamagePacket")
                                  : nullptr;
                const int raw = actor->getNumericProperty("enemyRoleAttackBudget");
                const bool effect = actor->getBoolProperty("octobogzPulseEffectApplied");
                json linkedEffect = nullptr;
                auto victim = player.lock();
                StatsModifier expectedBonus;
                expectedBonus.shadowResist = -1;
                auto victimMap = victim ? victim->getMap() : nullptr;
                if (victimMap && victimMap->getPlayer() == victim &&
                    victimMap->getObjectByName(victim->getName()) == victim) {
                    for (const auto &active : victim->getEffects()) {
                        // A one-turn effect still contributes at zero until the next native removal pass.
                        if (active && active->getTypeId() == "octobogzShadowPulseEffect" &&
                            active->getCaster() == actor && active->getVictim() == victim &&
                            active->getDuration() == 1 && active->getTimeLeft() >= 0 && active->getTimeLeft() <= 1 &&
                            active->getTimeTotal() == 1 && active->getBonus() &&
                            active->getBonus()->modifier() == expectedBonus) {
                            linkedEffect = {{"typeId", active->getTypeId()},
                                            {"caster", active->getCaster()->getName()},
                                            {"victim", active->getVictim()->getName()},
                                            {"duration", active->getDuration()},
                                            {"time", active->getTimeLeft()},
                                            {"timeTotal", active->getTimeTotal()},
                                            {"bonus", *object_serialize(active->getBonus())}};
                            break;
                        }
                    }
                }
                json observation = {{"slot", entry.slot},
                                    {"name", actor->getName()},
                                    {"damage_roll", raw},
                                    {"normal", packet ? packet->getNormal() : 0},
                                    {"shadow", packet ? packet->getShadow() : 0},
                                    {"pulse", pulse},
                                    {"effect", effect},
                                    {"linkedEffect", linkedEffect},
                                    {"enemyManaBefore", entry.mana},
                                    {"enemyManaAfter", mana},
                                    {"phaseBefore", entry.phase},
                                    {"phaseAfter", phase}};
                pulseObservations[pulseObservations.size()] = observation;
                if (raw > 0 && packet && packet->getNormal() == raw - 1 && packet->getShadow() == 1 && effect &&
                    !linkedEffect.is_null() && packet->getFire() == 0 && packet->getFrost() == 0 &&
                    packet->getThunder() == 0 && entry.phase == "charged" && phase == "spent" &&
                    entry.mana - mana == 5 && entry.items == actor->getItems()) {
                    positivePackets[positivePackets.size()] = observation;
                }
            }
            entry.mana = mana;
            entry.phase = phase;
            entry.pulse = pulse;
            entry.items = actor->getItems();
        }
    }

    void start(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override { observe(); }
    void end(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override { observe(); }
    void setOpponents(std::shared_ptr<CCreature>, const std::vector<std::shared_ptr<CCreature>> &) override {
        observe();
    }

    std::shared_ptr<CCreature> selectOpponent(std::shared_ptr<CCreature> me,
                                              const std::vector<std::shared_ptr<CCreature>> &opponents,
                                              std::shared_ptr<CCreature> opponent) override {
        observe();
        for (const auto &candidate : opponents) {
            if (candidate->getStringProperty("octobogzHuntSlot") == "brood" &&
                !candidate->getBoolProperty("octobogzPulseUsed")) {
                return candidate;
            }
        }
        return CFightController::selectOpponent(me, opponents, opponent);
    }

    bool control(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) override {
        observe();
        auto map = me ? me->getMap() : nullptr;
        requireHuntDecision(
            map && me->isPlayer() && opponent && opponent->isAlive() && me->getGame()->getMap() == map &&
                map->getPlayer() == me && map->getObjectByName(me->getName()) == me && opponent->getMap() == map &&
                map->getObjectByName(opponent->getName()) == opponent && me->getCoords() == opponent->getCoords() &&
                std::ranges::any_of(actors, [&](const auto &entry) { return entry.actor == opponent; }),
            "manual decisions require the actual registered player and hunt opponent in one fight cell");
        const auto slot = opponent->getStringProperty("octobogzHuntSlot");
        const auto phase = opponent->getStringProperty("octobogzCombatPhase");
        const int turn = ++playerTurns[opponent->getName()];
        const bool chooseBarrier = (slot == "brood" && turn <= 2) || (slot == "alpha" && phase == "charged");
        requireHuntDecision(decisions.size() < 256, "manual hunt decisions exceeded their fixed observation bound");
        if (!chooseBarrier && me->getHpRatio() < 50) {
            std::vector<std::shared_ptr<CItem>> healingItems;
            for (const auto &item : me->getItems()) {
                if (item && carriedItems.contains(item) && item->hasTag(CTag::Heal) && !item->hasTag(CTag::Mana) &&
                    item->isDisposable() && item->getBoolProperty("singleUse") && item->getPower() > 0) {
                    healingItems.push_back(item);
                }
            }
            std::sort(healingItems.begin(), healingItems.end(), [](const auto &left, const auto &right) {
                return std::tuple(-left->getPower(), left->getTypeId(), left->getName()) <
                       std::tuple(-right->getPower(), right->getTypeId(), right->getName());
            });
            if (!healingItems.empty()) {
                const auto item = healingItems.front();
                requireHuntDecision(carriedItems.contains(item) && me->hasInInventory(item),
                                    "manual recovery must consume an item genuinely carried in the loaded save");
                const int hpBefore = me->getHp();
                const int hpMax = me->getHpMax();
                const int manaBefore = me->getMana();
                const int enemyHpBefore = opponent->getHp();
                const int enemyManaBefore = opponent->getMana();
                const auto inventoryCountBefore = me->getItems().size();
                const int healAmount = std::max(1, static_cast<int>(item->getPower() * 20 / 100.0 * hpMax));
                me->useItem(item);
                requireHuntDecision(!me->hasInInventory(item) && me->getItems().size() + 1 == inventoryCountBefore,
                                    "native useItem must consume the actual carried healing item exactly once");
                requireHuntDecision(
                    me->getHp() > hpBefore && me->getHp() == std::min(hpMax, hpBefore + healAmount) &&
                        me->getMana() == manaBefore && opponent->getHp() == enemyHpBefore &&
                        opponent->getMana() == enemyManaBefore,
                    "the ordinary healing item must restore its capped percentage without other grants");
                decisions[decisions.size()] = {{"action", "UseItem"},
                                               {"slot", slot},
                                               {"target", opponent->getName()},
                                               {"round", map->getNumericProperty("combatRound")},
                                               {"phase", phase},
                                               {"item", huntItemIdentity(item)},
                                               {"consumedOnce", true},
                                               {"healOnlyDisposable", true},
                                               {"inventoryCountBefore", inventoryCountBefore},
                                               {"inventoryCountAfter", me->getItems().size()},
                                               {"hpBefore", hpBefore},
                                               {"hpAfter", me->getHp()},
                                               {"hpMax", hpMax},
                                               {"manaBefore", manaBefore},
                                               {"manaAfter", me->getMana()},
                                               {"cost", 0},
                                               {"refund", 0},
                                               {"enemyHpBefore", enemyHpBefore},
                                               {"enemyHpAfter", opponent->getHp()},
                                               {"enemyManaBefore", enemyManaBefore},
                                               {"enemyManaAfter", opponent->getMana()}};
                observe();
                return true;
            }
        }
        const std::string actionId = chooseBarrier ? "Barrier" : "Attack";
        const auto actions = me->getEffectiveInteractions();
        const auto selected =
            std::ranges::find_if(actions, [&](const auto &action) { return action->getTypeId() == actionId; });
        requireHuntDecision(selected != actions.end(), "manual decisions must select an actual learned action");
        const auto action = *selected;
        const int cost = action->getManaCost();
        const int manaBefore = me->getMana();
        const int hpBefore = me->getHp();
        const int enemyHpBefore = opponent->getHp();
        const int enemyManaBefore = opponent->getMana();
        requireHuntDecision(cost >= 0 && manaBefore >= cost, "the loaded hero must pay its configured action cost");
        const int refund = std::clamp(action->getCommittedManaRefund(me), 0, cost);
        if (chooseBarrier) {
            requireHuntDecision(cost == 17, "the learned Barrier must retain its full configured mana cost");
            if (slot == "brood") {
                requireHuntDecision(enemyHpBefore == opponent->getHpMax(),
                                    "the first two Barrier decisions must leave the actual Brood at full health");
            }
        }
        me->useAction(action, opponent);
        requireHuntDecision(opponent->getMana() == enemyManaBefore,
                            "a player decision must not change the enemy's mana payment");
        requireHuntDecision(manaBefore - me->getMana() == cost - refund,
                            "native useAction must pay and refund the real configured action cost");
        if (chooseBarrier) {
            requireHuntDecision(
                std::ranges::any_of(me->getEffects(),
                                    [](const auto &effect) { return effect->getTypeId() == "BarrierEffect"; }),
                "a paid Barrier decision must apply its actual configured effect");
            requireHuntDecision(me->getStats()->getNormalResist() != me->getStats()->getShadowResist(),
                                "the paid Barrier must leave unequal real wards for the shadow packet");
            ++paidBarriers;
        }
        decisions[decisions.size()] = {{"action", actionId},
                                       {"slot", slot},
                                       {"target", opponent->getName()},
                                       {"round", me->getMap()->getNumericProperty("combatRound")},
                                       {"phase", phase},
                                       {"manaBefore", manaBefore},
                                       {"manaAfter", me->getMana()},
                                       {"cost", cost},
                                       {"refund", refund},
                                       {"hpBefore", hpBefore},
                                       {"hpAfter", me->getHp()},
                                       {"enemyHpBefore", enemyHpBefore},
                                       {"enemyHpAfter", opponent->getHp()}};
        observe();
        return true;
    }

    json decisions = json::array();
    json pulseObservations = json::array();
    json positivePackets = json::array();
    int paidBarriers = 0;
    std::vector<HuntDecisionActor> actors;

  private:
    std::weak_ptr<CPlayer> player;
    const std::set<std::shared_ptr<CItem>> carriedItems;
    std::map<std::string, int> playerTurns;
};

void walkHuntDecisionToActor(const std::shared_ptr<CGame> &game, const std::shared_ptr<CMap> &map,
                             const std::shared_ptr<CPlayer> &player, const std::shared_ptr<CCreature> &enemy,
                             int &movements, const std::string &defeatReceipt) {
    while (enemy->isAlive() && map->getObjectByName(enemy->getName()) == enemy) {
        requireHuntDecision(movements < 512, "manual hunt movement exceeded its bounded adjacent route");
        const auto origin = player->getCoords();
        const auto goal = enemy->getCoords();
        requireHuntDecision(origin != goal, "the loaded player must approach the hostile cell by an actual step");
        auto passable = [map, player, goal](Coords coords) {
            if (!map->isWithinBounds(coords) || !map->canStep(coords)) {
                return false;
            }
            bool unintendedHostile = false;
            if (coords != goal) {
                map->forObjectsAtCoords(coords, [&](const auto &object) {
                    auto creature = std::dynamic_pointer_cast<CCreature>(object);
                    unintendedHostile |= creature && creature != player && creature->isAlive() && !creature->isNpc() &&
                                         !player->isAffiliatedWith(creature);
                });
            }
            return !unintendedHostile;
        };
        const auto path = CNavigationSearch::findGenericPath(
            origin, goal, passable, [](const Coords &) { return std::optional<Coords>(); },
            [map](const Coords &coords) { return map->getAdjacentCoords(coords); }, CPathFinder::mapHeuristic(map),
            [map](const Coords &from, const Coords &to) { return map->lookupNavigationStepCost(from, to); },
            map->getNavigationService()->budget(), CNavigationSearchLimits{4096, 4096, 512});
        requireHuntDecision(path.status == CNavigationSearchStatus::Found && !path.path.empty(),
                            "the native walkability search must find a bounded route to the actual hunt actor");
        const auto next = path.path.front();
        const auto delta = map->getShortestDelta(origin, next);
        requireHuntDecision(delta.z == 0 && std::abs(delta.x) + std::abs(delta.y) == 1 && map->canStep(next),
                            "every manual witness movement must use a passable cardinal neighbor");
        // Stepping onto the living actor invokes the production fight and its initiative exactly once.
        player->moveTo(next);
        vstd::event_loop<>::instance()->run();
        ++movements;
        requireHuntDecision(game->getMap() == map && map->getPlayer() == player && player->isAlive() &&
                                player->getUiDefeatReceipt() == defeatReceipt,
                            "manual witness movement must not accept death, respawn or a map transition");
        const int turn = map->getTurn();
        map->move();
        vstd::event_loop<>::instance()->run();
        requireHuntDecision(map->getTurn() == turn + 1 && game->getMap() == map && map->getPlayer() == player &&
                                player->isAlive() && player->getUiDefeatReceipt() == defeatReceipt,
                            "each manual adjacent step must preserve a real living player through its native turn");
        const auto arrivalDelta = map->getShortestDelta(origin, player->getCoords());
        requireHuntDecision(arrivalDelta.z == 0 && std::abs(arrivalDelta.x) + std::abs(arrivalDelta.y) <= 1,
                            "the manual witness must not jump or accept an unobserved relocation");
    }
}

void testManualHuntDecisionFromEarnedSave(const std::string &saveSlot) {
    json report = {{"mode", "deterministic-manual-earned-save"}, {"saveSlot", saveSlot}, {"seed", 100}};
    const int previousFailures = failures;
    struct RestoreNativeRng {
        std::decay_t<decltype(vstd::rng())> previous = vstd::rng();
        ~RestoreNativeRng() { vstd::rng() = previous; }
    } restoreRng;
    std::shared_ptr<CGame> game;
    std::shared_ptr<CPlayer> player;
    std::shared_ptr<CFightController> ordinaryController;
    std::shared_ptr<HuntDecisionController> controller;
    std::string defeatReceipt;
    std::string primaryBytes;
    int movements = 0;
    try {
        requireHuntDecision(CSaveFormat::isValidSlotName(saveSlot), "manual witness requires a valid save slot");
        game = CGameLoader::loadGame();
        auto resources = game->getResourcesProvider();
        const auto primaryPath = CSaveFormat::primaryPath(saveSlot);
        requireHuntDecision(!resources->getPath(primaryPath).empty() &&
                                resources->getPath(CSaveFormat::backupPath(saveSlot)).empty(),
                            "manual replay requires a unique valid primary without backup-repair fallback");
        primaryBytes = resources->load(primaryPath);
        auto decoded = CSaveFormat::decodeDocument(std::make_shared<json>(json::parse(primaryBytes)));
        requireHuntDecision(decoded.has_value() && decoded->mapName == "nouraajd",
                            "manual replay must load the earned primary Nouraajd save");
        CGameLoader::loadSavedGame(game, saveSlot);
        auto map = game->getMap();
        requireHuntDecision(map && map->getMapName() == "nouraajd", "the supplied primary save must actually load");
        player = map->getPlayer();
        requireHuntDecision(player && player->isAlive() && player->getPlayerClassId() == "Warrior",
                            "manual replay requires the genuinely earned living Warrior");
        report["playerBefore"] = huntPlayerSnapshot(player);
        report["playerComposedStatsBefore"] = *object_serialize(player->getStats());
        defeatReceipt = player->getUiDefeatReceipt();
        report["defeatReceiptBefore"] = defeatReceipt;
        const auto registryText = map->getStringProperty("octobogzHuntRegistry");
        const std::string registryPrefix = "octobogzHunt.v1:";
        requireHuntDecision(registryText.starts_with(registryPrefix),
                            "the partial save must retain its actual registry");
        const auto registry = json::parse(registryText.substr(registryPrefix.size()));
        report["registryBefore"] = registryText;
        report["actorsBefore"] = json::array();
        std::vector<HuntDecisionActor> actors;
        for (const auto &slot : {"alpha", "brood", "scout"}) {
            const auto &record = registry.at("slots").at(slot);
            if (record.at("status").get<std::string>() != "living") {
                continue;
            }
            auto actor =
                std::dynamic_pointer_cast<CCreature>(map->getObjectByName(record.at("name").get<std::string>()));
            requireHuntDecision(actor && actor->isAlive() && actor->getTypeId() == "OctoBogz" &&
                                    actor->getStringProperty("octobogzHuntSlot") == slot,
                                "each loaded living registry identity must match the actual hunt actor");
            actors.push_back({slot, actor, actor->getFightController(), actor->getMana(),
                              actor->getStringProperty("octobogzCombatPhase"),
                              actor->getBoolProperty("octobogzPulseUsed"), actor->getItems()});
            auto &before = report["actorsBefore"];
            before[before.size()] = {{"slot", slot},
                                     {"name", actor->getName()},
                                     {"typeId", actor->getTypeId()},
                                     {"level", actor->getLevel()},
                                     {"hp", actor->getHp()},
                                     {"mana", actor->getMana()},
                                     {"phase", actor->getStringProperty("octobogzCombatPhase")},
                                     {"role", actor->getStringProperty("octobogzCombatRole")}};
        }
        const auto learned = player->getEffectiveInteractions();
        for (const auto &actionId : {"Attack", "Barrier"}) {
            requireHuntDecision(
                std::ranges::any_of(learned, [&](const auto &action) { return action->getTypeId() == actionId; }),
                "the earned Warrior must already know its configured Attack and Barrier");
        }
        ordinaryController = player->getFightController();
        controller = std::make_shared<HuntDecisionController>(player, actors);
        player->setFightController(controller);
        requireHuntDecision(report["playerBefore"].dump() == huntPlayerSnapshot(player).dump() &&
                                report["playerComposedStatsBefore"].dump() ==
                                    object_serialize(player->getStats())->dump() &&
                                map->getStringProperty("octobogzHuntRegistry") == registryText,
                            "installing the decision controller must preserve every loaded hero field and registry");
        // This is one deterministic replay of the earned save, independent of the unchanged automatic victories.
        // The C RNG belongs to this isolated CLI process; the native generator is restored on exit.
        vstd::rng().seed(100);
        std::srand(100);
        for (const auto &slot : {"brood", "alpha"}) {
            auto target = std::ranges::find_if(actors, [&](const auto &entry) { return entry.slot == slot; });
            if (target == actors.end() || !target->actor->isAlive() ||
                target->actor->getBoolProperty("octobogzPulseUsed")) {
                continue;
            }
            walkHuntDecisionToActor(game, map, player, target->actor, movements, defeatReceipt);
            controller->observe();
            requireHuntDecision(!target->actor->isAlive() && !map->getObjectByName(target->actor->getName()),
                                "the movement encounter must actually defeat and remove its selected hunt actor");
            const auto after = map->getStringProperty("octobogzHuntRegistry");
            const auto state = json::parse(after.substr(registryPrefix.size()));
            requireHuntDecision(state.at("slots").at(slot).at("status").get<std::string>() == "dead",
                                "only the actual defeat trigger may register this hunt slot as dead");
            if (!controller->positivePackets.empty()) {
                break;
            }
        }
        requireHuntDecision(movements > 0 && controller->paidBarriers > 0 && !controller->positivePackets.empty(),
                            "manual replay must witness a paid Barrier and a positive native five-mana shadow pulse");
        for (const auto &entry : controller->actors) {
            requireHuntDecision(entry.actor->getFightController() == entry.controller,
                                "manual replay must leave every enemy's configured controller unchanged");
        }
        requireHuntDecision(resources->load(primaryPath) == primaryBytes,
                            "manual replay must not overwrite its input save");
        report["sourceUnchanged"] = true;
        report["registryAfter"] = map->getStringProperty("octobogzHuntRegistry");
    } catch (const std::exception &error) {
        report["error"] = error.what();
        expect_true(false, error.what());
    }
    report["movements"] = movements;
    report["cardinalVerified"] = movements > 0 && failures == previousFailures;
    report["playerAlive"] = player && player->isAlive();
    report["defeatReceiptUnchanged"] = player && player->getUiDefeatReceipt() == defeatReceipt;
    if (controller) {
        report["paidBarriers"] = controller->paidBarriers;
        report["decisions"] = controller->decisions;
        report["pulseObservations"] = controller->pulseObservations;
        report["positivePackets"] = controller->positivePackets;
    }
    report["success"] = failures == previousFailures;
    if (player && ordinaryController) {
        player->setFightController(ordinaryController);
    }
    if (game) {
        game->getContext()->shutdown();
    }
    std::cout << "NATIVE_HUNT_DECISION_RESULT " << report.dump() << std::endl;
}
} // namespace

int main(int argc, char **argv) {
    const bool contractsOnly = argc == 2 && std::string(argv[1]) == "--contracts-only";
    const bool huntRoute = argc == 2 && std::string(argv[1]) == "--hunt-route";
    const bool huntDecision = argc == 3 && std::string(argv[1]) == "--hunt-decision";
    std::string selectedClass;
    if (argc == 3 && std::string(argv[1]) == "--role-class") {
        selectedClass = argv[2];
        const std::vector<std::string> classes{"Warrior", "Sorcerer", "Assasin", "Inquisitor", "Wayfarer"};
        if (std::find(classes.begin(), classes.end(), selectedClass) == classes.end()) {
            std::cerr << "Unknown role class partition\n";
            return 1;
        }
    } else if (argc != 1 && !contractsOnly && !huntRoute && !huntDecision) {
        std::cerr << "Usage: monster_balance_unit_tests [--contracts-only | --role-class CLASS | --hunt-route | "
                     "--hunt-decision SAVE_SLOT]\n";
        return 1;
    }
    if (PyImport_AppendInittab("_game", PyInit__game) != 0) {
        std::cerr << "Cannot register the real embedded _game module\n";
        return 1;
    }
    pybind11::scoped_interpreter interpreter{};
    initializeBalancePythonContent();
    if (huntDecision) {
        testManualHuntDecisionFromEarnedSave(argv[2]);
        return finish_tests();
    }
    if (selectedClass.empty()) {
        testInheritedNativeMethodsDoNotBecomePythonOverrides();
        testRolePacketKeepsRandomStreamsAndConfiguredAttackWeaponCallbacks();
        testRolePacketKeepsRandomStreamsAndConfiguredAttackWeaponCallbacks(false, true);
        testRolePacketKeepsRandomStreamsAndConfiguredAttackWeaponCallbacks(false, true, false, true);
        testRolePacketKeepsRandomStreamsAndConfiguredAttackWeaponCallbacks(false, true, false, false, 9);
        testRolePacketKeepsRandomStreamsAndConfiguredAttackWeaponCallbacks(false, true, false, false, 10);
        testCultistShadowPacketAndExpiryFollowActualFightInitiativeBoundaries();
        testObserverRetainsDamageConsumptionAndForwardsOrdinaryControllerCalls();
        testActivePlayerNeverUsesMonsterSignature();
    }
    if (huntRoute) {
        testRolePacketKeepsRandomStreamsAndConfiguredAttackWeaponCallbacks(false, false, true);
        testRolePacketKeepsRandomStreamsAndConfiguredAttackWeaponCallbacks(true);
        testRolePacketKeepsRandomStreamsAndConfiguredAttackWeaponCallbacks(true, false, false, true);
        testCultistShadowPacketAndExpiryFollowActualFightInitiativeBoundaries(true);
        testStagedHuntPreservesOriginalThreeActorRouteWinsAndResourceBudget();
    } else if (!contractsOnly) {
        testMonsterRolesPreserveOrdinaryLoadoutWinsAndResourceBudget(selectedClass);
    }
    const int result = finish_tests();
    if (contractsOnly && result == 0) {
        std::cout << "role contracts complete\n";
    }
    return result;
}
