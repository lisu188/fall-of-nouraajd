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

struct RoleBalanceSample {
    bool won;
    int healthSpent;
    int manaSpent;
    int itemsSpent;
    double setupMilliseconds;
    double fightMilliseconds;
    double cleanupMilliseconds;
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
                            std::shared_ptr<PlayerResourceObserver> observer)
        : delegate(std::move(delegate)), observer(std::move(observer)) {}

    bool control(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) override {
        observer->observe();
        const bool result = delegate->control(me, opponent);
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
    player->setFightController(std::make_shared<ObservedFightController>(ordinaryController, observer));
    enemy->setFightController(std::make_shared<ObservedFightController>(enemy->getFightController(), observer));
    vstd::rng().seed(seed);
    std::srand(seed);
    const auto fightStarted = std::chrono::steady_clock::now();
    const auto result = CFightHandler::fightManyResult(player, {enemy});
    observer->observe();
    const auto cleanupStarted = std::chrono::steady_clock::now();
    RoleBalanceSample sample{
        result.attackerSucceeded(), observer->healthSpent, observer->manaSpent, observer->itemsSpent, 0, 0, 0};
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

void initializeBalancePythonContent() {
    std::cerr << "monster balance: initializing bindings\n";
    auto sys = pybind11::module_::import("sys");
    sys.attr("path").attr("insert")(0, GAME_MONSTER_BALANCE_TEST_RESOURCE_ROOT);
    const auto nativeModule = pybind11::module_::import("_game");
    expect_true(nativeModule.attr("CInteraction").attr("__module__").cast<std::string>() == "_game",
                "embedded native classes must have the production module identity");
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

void testMonsterRolesPreserveOrdinaryLoadoutWinsAndResourceBudget() {
    const auto previousRng = vstd::rng();
    auto game = CGameLoader::loadGame();
    createOpenBalanceMap(game);
    auto median = [](std::vector<int> values) {
        std::sort(values.begin(), values.end());
        return values[values.size() / 2];
    };
    for (const auto &playerType : {"Warrior", "Sorcerer", "Assasin", "Inquisitor", "Wayfarer"}) {
        bool classHasMandatoryBaselineWitness = false;
        for (const auto &monsterType :
             {"Gooby", "Pritz", "OctoBogz", "PritzMage", "GoblinThief", "Cultist", "CultLeader"}) {
            std::vector<int> baselineHp, roleHp, baselineMana, roleMana, baselineItems, roleItems;
            int baselineWins = 0;
            double setupMilliseconds = 0, fightMilliseconds = 0, cleanupMilliseconds = 0;
            for (unsigned seed = 100; seed < 111; ++seed) {
                const auto baseline = runRoleBalanceFight(game, playerType, monsterType, seed, false);
                const auto roles = runRoleBalanceFight(game, playerType, monsterType, seed, true);
                baselineWins += baseline.won ? 1 : 0;
                setupMilliseconds += baseline.setupMilliseconds + roles.setupMilliseconds;
                fightMilliseconds += baseline.fightMilliseconds + roles.fightMilliseconds;
                cleanupMilliseconds += baseline.cleanupMilliseconds + roles.cleanupMilliseconds;
                if (baseline.won && !roles.won) {
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
        }
        expect_true(classHasMandatoryBaselineWitness,
                    "each class must win against a representative authored enemy that also causes baseline damage");
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

int main() {
    if (PyImport_AppendInittab("_game", PyInit__game) != 0) {
        std::cerr << "Cannot register the real embedded _game module\n";
        return 1;
    }
    pybind11::scoped_interpreter interpreter{};
    initializeBalancePythonContent();
    testInheritedNativeMethodsDoNotBecomePythonOverrides();
    testObserverRetainsDamageConsumptionAndForwardsOrdinaryControllerCalls();
    testActivePlayerNeverUsesMonsterSignature();
    testMonsterRolesPreserveOrdinaryLoadoutWinsAndResourceBudget();
    return finish_tests();
}
