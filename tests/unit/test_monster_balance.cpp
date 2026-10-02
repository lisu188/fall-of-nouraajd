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
#include "core/CLoader.h"
#include "core/CMap.h"
#include "core/CPythonOverrides.h"
#include "core/CStats.h"
#include "handler/CFightHandler.h"
#include "object/CCreature.h"
#include "object/CCreatureClass.h"
#include "object/CEffect.h"
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

void testRolePacketKeepsRandomStreamsAndConfiguredAttackWeaponCallbacks(bool cultistHex = false,
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
            auto actor = game->createObject<CCreature>(cultistHex ? "Cultist" : "PritzMage");
            actor->setName("roleContractActor");
            actor->setLevel(2);
            actor->setPosX(1);
            game->getMap()->addObject(actor);
            actor->setMana(cultistHex ? 5 : 0);
            actor->setBoolProperty("enemyRoleUsed", !enabled);
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
            const auto interactions = actor->getInteractions();
            const auto attackIt =
                std::ranges::find_if(interactions, [](const auto &action) { return action->getTypeId() == "Attack"; });
            if (attackIt == interactions.end() || !weapon->getInteraction()) {
                expect_true(false, "role contract fixture must load real Attack and configured Staff interaction");
                return;
            }
            const auto attack = *attackIt;
            const auto signatureIt = std::ranges::find_if(interactions, [cultistHex](const auto &action) {
                return action->getTypeId() == (cultistHex ? "enemyRitualHex" : "enemyArcaneBolt");
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
            const auto recipient = cultistHex ? vstd::cast<CCreature>(player) : actor;
            const int beforeResist =
                cultistHex ? recipient->getStats()->getShadowResist() : recipient->getStats()->getNormalResist();
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
                expect_true(signatureIt != interactions.end() &&
                                !(*signatureIt)->getObjectProperty<CGameObject>("roleEffect"),
                            "consumed eager effects must transfer out of the actor-owned signature slot");
                const int afterResist =
                    cultistHex ? recipient->getStats()->getShadowResist() : recipient->getStats()->getNormalResist();
                expect_true(afterResist == beforeResist - 1 && recipient->getEffects().size() == 1,
                            "the one-turn signature tradeoff must actually affect combat stats");
                if (!recipient->getEffects().empty()) {
                    const auto effect = *recipient->getEffects().begin();
                    expect_true(effect->getTimeLeft() == 1 && effect->getCaster() == actor &&
                                    effect->getVictim() == recipient,
                                "the eagerly owned effect must have a real duration and actor endpoints");
                    effect->apply(recipient);
                    expect_true(effect->getTimeLeft() == 0, "the role effect must expire after one application");
                }
            } else {
                expectedNativeRng = afterNativeRng;
                expectedNextBlockRoll = nextBlockRoll;
                expectedWeaponCalls = weaponCalls;
                expectedPlayerHp = player->getHp();
                const int afterResist =
                    cultistHex ? recipient->getStats()->getShadowResist() : recipient->getStats()->getNormalResist();
                expect_true(recipient->getEffects().empty() && afterResist == beforeResist,
                            "disabled roles must leave ordinary Attack stats unchanged");
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

void testCultistShadowPacketAndExpiryFollowActualFightInitiativeBoundaries() {
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

            auto actor = game->createObject<CCreature>("Cultist");
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
                        "the one-turn hex must affect one actual victim turn and expire at its next turn boundary");
            expect_true(player->getEffects().empty() && player->getStats()->getShadowResist() == 0,
                        "actual fight expiry must restore target resistance and remove the linked effect");
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
                if (std::string(playerType) == "Wayfarer" && std::string(monsterType) == "OctoBogz" && seed == 109) {
                    expect_true(baseline.won && roles.won,
                                "deterministic effect ticks must preserve the historical seed 109 baseline victory");
                }
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
} // namespace

int main(int argc, char **argv) {
    const bool contractsOnly = argc == 2 && std::string(argv[1]) == "--contracts-only";
    std::string selectedClass;
    if (argc == 3 && std::string(argv[1]) == "--role-class") {
        selectedClass = argv[2];
        const std::vector<std::string> classes{"Warrior", "Sorcerer", "Assasin", "Inquisitor", "Wayfarer"};
        if (std::find(classes.begin(), classes.end(), selectedClass) == classes.end()) {
            std::cerr << "Unknown role class partition\n";
            return 1;
        }
    } else if (argc != 1 && !contractsOnly) {
        std::cerr << "Usage: monster_balance_unit_tests [--contracts-only | --role-class CLASS]\n";
        return 1;
    }
    if (PyImport_AppendInittab("_game", PyInit__game) != 0) {
        std::cerr << "Cannot register the real embedded _game module\n";
        return 1;
    }
    pybind11::scoped_interpreter interpreter{};
    initializeBalancePythonContent();
    if (selectedClass.empty()) {
        testInheritedNativeMethodsDoNotBecomePythonOverrides();
        testRolePacketKeepsRandomStreamsAndConfiguredAttackWeaponCallbacks();
        testRolePacketKeepsRandomStreamsAndConfiguredAttackWeaponCallbacks(true);
        testRolePacketKeepsRandomStreamsAndConfiguredAttackWeaponCallbacks(true, true);
        testRolePacketKeepsRandomStreamsAndConfiguredAttackWeaponCallbacks(true, false, 9);
        testRolePacketKeepsRandomStreamsAndConfiguredAttackWeaponCallbacks(true, false, 10);
        testCultistShadowPacketAndExpiryFollowActualFightInitiativeBoundaries();
        testObserverRetainsDamageConsumptionAndForwardsOrdinaryControllerCalls();
        testActivePlayerNeverUsesMonsterSignature();
    }
    if (!contractsOnly) {
        testMonsterRolesPreserveOrdinaryLoadoutWinsAndResourceBudget(selectedClass);
    }
    const int result = finish_tests();
    if (contractsOnly && result == 0) {
        std::cout << "role contracts complete\n";
    }
    return result;
}
