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
#pragma once

void testCombatObserversRunAfterAllDamageAndProcsAndStopAfterInvalidation() {
    for (const auto &mode : {"generation", "removal", "transfer", "shutdown"}) {
        auto game = load_empty_game();
        auto foreign = load_empty_game();
        auto map = game->getMap();
        auto attacker = add_test_creature(game, "unitBoundaryAttacker");
        auto victim = add_test_creature(game, "unitBoundaryVictim", 1, 0);
        auto swing = std::make_shared<NativePhysicalSwingProbe>();
        swing->setGame(game);
        swing->setOffensive(true);
        attacker->addAction(swing);
        auto weapon_action = std::make_shared<NativeArmorPacketProbe>();
        weapon_action->setGame(game);
        weapon_action->setOffensive(true);
        auto weapon = std::make_shared<CWeapon>();
        weapon->setGame(game);
        weapon->setName("unitBoundaryWeapon");
        weapon->setInteraction(weapon_action);
        attacker->addItem(weapon);
        attacker->setWeapon(weapon);
        auto armor_action = std::make_shared<NativeArmorPacketProbe>();
        armor_action->setGame(game);
        armor_action->setOffensive(true);
        auto armor = std::make_shared<CArmor>();
        armor->setGame(game);
        armor->setName("unitBoundaryArmor");
        armor->setInteraction(armor_action);
        victim->addItem(armor);
        victim->setArmor(armor);
        auto stats = attacker->getBaseStats();
        stats->setDmgMin(2);
        stats->setDmgMax(2);
        stats->setDamage(0);
        stats->setAttack(0);
        stats->setHit(100);
        stats->setCrit(0);
        attacker->getBaseStats()->setBlock(0);
        victim->getBaseStats()->setBlock(0);
        int callbacks = 0;
        int hp_at_callback = -1;
        int attacker_hp_at_callback = -1;
        for (int i = 0; i < 2; ++i) {
            auto trigger = std::make_shared<CCustomTrigger>(victim->getName(), "onCombatAttempt", [&](auto, auto) {
                ++callbacks;
                hp_at_callback = victim->getHp();
                attacker_hp_at_callback = attacker->getHp();
                expect_true(weapon_action->performed == 1 && armor_action->performed == 1 && hp_at_callback == 7 &&
                                attacker_hp_at_callback == 9,
                            "the first observer runs only after the primary packet and real weapon/armor procs");
                if (std::string(mode) == "generation") {
                    game->getContext()->advanceTransitionGeneration();
                } else if (std::string(mode) == "shutdown") {
                    game->getContext()->shutdown();
                } else {
                    map->removeObject(victim);
                    if (std::string(mode) == "transfer") {
                        victim->setGame(foreign);
                        foreign->getMap()->addObject(victim);
                    }
                }
            });
            trigger->setName("unitBoundaryCancel_" + std::to_string(i));
            map->getEventHandler()->registerTrigger(trigger);
        }
        map->setBoolProperty("nativeCombatFacts", true);
        attacker->useAction(swing, victim);
        expect_true(callbacks == 1 && victim->getHp() == hp_at_callback &&
                        attacker->getHp() == attacker_hp_at_callback && weapon_action->performed == 1 &&
                        armor_action->performed == 1,
                    "invalidation stops later listeners and facts; no old damage or proc runs after the observer");
    }
}

void testCombatObserverRegistrationUsesStableSnapshotAndImmutableFactCopies() {
    auto game = load_empty_game();
    auto map = game->getMap();
    auto attacker = add_test_creature(game, "unitRegistrationAttacker");
    auto victim = add_test_creature(game, "unitRegistrationVictim", 1, 0);
    auto action = std::make_shared<CommittedOffensiveProbe>();
    action->setGame(game);
    action->setOffensive(true);
    int original = 0;
    int late = 0;
    bool inserted = false;
    for (int i = 0; i < 2; ++i) {
        auto hook = std::make_shared<CCustomTrigger>(victim->getName(), "onCombatAttempt", [&](auto, auto event) {
            ++original;
            expect_true(event->getNumericProperty("combatManaAtCommit") == 0,
                        "each listener receives a fresh copy of the original immutable native capture");
            event->setNumericProperty("combatManaAtCommit", 999);
            if (!inserted) {
                inserted = true;
                auto next =
                    std::make_shared<CCustomTrigger>(victim->getName(), "onCombatAttempt", [&](auto, auto event) {
                        expect_true(event->getNumericProperty("combatManaAtCommit") == 0,
                                    "a newly registered listener also receives the original capture");
                        ++late;
                    });
                next->setName("unitRegistrationLate");
                map->getEventHandler()->registerTrigger(next);
                for (int index = 0; index < 1024; ++index) {
                    auto unrelated = std::make_shared<CCustomTrigger>("unrelated" + std::to_string(index),
                                                                      "onCombatAttempt", [](auto, auto) {});
                    unrelated->setName("unitRegistrationRehash_" + std::to_string(index));
                    map->getEventHandler()->registerTrigger(unrelated);
                }
            }
        });
        hook->setName("unitRegistrationOriginal_" + std::to_string(i));
        map->getEventHandler()->registerTrigger(hook);
    }
    map->setBoolProperty("nativeCombatFacts", true);
    attacker->setMana(0);
    action->onAction(attacker, victim);
    expect_true(original == 2 && late == 0, "rehashing registration cannot alter the current listener snapshot");
    action->onAction(attacker, victim);
    expect_true(original == 4 && late == 1, "the next completed action observes the new listener exactly once");
}

void testCombatBatchNestingAbandonmentAndFactCapacity() {
    auto game = load_empty_game();
    auto map = game->getMap();
    auto attacker = add_test_creature(game, "unitBatchAttacker");
    auto victim = add_test_creature(game, "unitBatchVictim", 1, 0);
    auto action = std::make_shared<CommittedOffensiveProbe>();
    action->setGame(game);
    action->setOffensive(true);
    int callbacks = 0;
    auto hook =
        std::make_shared<CCustomTrigger>(victim->getName(), "onCombatAttempt", [&](auto, auto) { ++callbacks; });
    hook->setName("unitBatchAttempt");
    map->getEventHandler()->registerTrigger(hook);
    map->setBoolProperty("nativeCombatFacts", true);
    {
        CNativeCombatScope outer(game);
        action->onAction(attacker, victim);
        expect_true(callbacks == 0 && action->performed == 1, "nested direct onAction does not flush a partial batch");
        outer.finish();
        expect_true(callbacks == 1, "outer completion releases its captured facts exactly once");
    }
    {
        CNativeCombatScope abandoned(game);
        action->onAction(attacker, victim);
    }
    expect_true(callbacks == 1 && action->performed == 2,
                "an abandoned boundary discards observations, not committed work");
    action->onAction(attacker, victim);
    expect_true(callbacks == 2, "abandonment releases the context batch for a fresh operation");

    int rolls = 0;
    auto roll = std::make_shared<CCustomTrigger>(victim->getName(), "onCombatRoll", [&](auto, auto) { ++rolls; });
    roll->setName("unitBatchRoll");
    map->getEventHandler()->registerTrigger(roll);
    {
        CNativeCombatScope full(game);
        for (int i = 0; i < 128; ++i)
            attacker->getDmgFor(victim);
        expect_true(rolls == 0, "128 genuine rolls are captured without mid-operation callbacks");
        full.finish();
    }
    expect_true(rolls == 128, "the inclusive 128-fact capacity must deliver every captured roll");
    bool refused = false;
    try {
        CNativeCombatScope overflow(game);
        for (int i = 0; i < 129; ++i)
            attacker->getDmgFor(victim);
        overflow.finish();
    } catch (const std::runtime_error &error) {
        refused = std::string(error.what()).find("fixed work budget") != std::string::npos;
    }
    expect_true(refused && rolls == 128,
                "the 129th fact explicitly fails without silently accepting a truncated batch");
    action->onAction(attacker, victim);
    expect_true(callbacks == 3, "capacity refusal leaves no stale context batch behind");
}
