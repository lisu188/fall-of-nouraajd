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

#include "core/CNativeCombatFacts.h"
#include "native_combat_attempt_regression.h"

void testNativeCombatRollDistinguishesZeroHitFromMissAndPreservesDice() {
    auto game = load_empty_game();
    auto map = game->getMap();
    auto attacker = add_test_creature(game, "unitRollAttacker");
    auto victim = add_test_creature(game, "unitRollVictim", 1, 0);
    auto stats = attacker->getBaseStats();
    stats->setAttack(0);
    stats->setDmgMin(0);
    stats->setDmgMax(0);
    stats->setDamage(0);
    int rolls = 0;
    bool expected_connected = true;
    map->getEventHandler()->registerTrigger(
        std::make_shared<CCustomTrigger>(victim->getName(), "onCombatRoll", [&](auto object, auto event) {
            auto caused = std::dynamic_pointer_cast<CGameEventCaused>(event);
            expect_true(object == victim && caused && caused->getCause() == attacker,
                        "roll delivery retains the native target and aggressor");
            expect_true(event->getBoolProperty("combatConnected") == expected_connected &&
                            event->getNumericProperty("combatDamage") == 0,
                        "zero damage must retain the actual native hit outcome independently of HP");
            ++rolls;
        }));
    map->setBoolProperty("nativeCombatFacts", true);
    const auto runRoll = [&](bool allowCrit = true) {
        CNativeCombatScope operation(game);
        const int damage = attacker->getDmgFor(victim, allowCrit);
        operation.finish();
        return damage;
    };
    attacker->getDmgFor(victim);
    expect_true(rolls == 0, "a bare numeric helper cannot publish before its unknown caller consumes its result");
    stats->setHit(100);
    expect_true(runRoll() == 0 && rolls == 1, "a zero-damage hit still records its roll");
    expected_connected = false;
    stats->setHit(0);
    expect_true(runRoll() == 0 && rolls == 2, "a miss records false without a second roll");

    map->setBoolProperty("nativeCombatFacts", false);
    stats->setHit(49);
    stats->setCrit(21);
    stats->setDmgMin(1);
    stats->setDmgMax(8);
    std::vector<int> legacy;
    srand(20261103u);
    for (int i = 0; i < 128; ++i)
        legacy.push_back(attacker->getDmg(i % 2 == 0));
    const int legacy_next = rand();
    srand(20261103u);
    for (int i = 0; i < 128; ++i)
        expect_true(runRoll(i % 2 == 0) == legacy[i],
                    "explicit rolls must preserve every legacy result with observations disabled");
    expect_true(rand() == legacy_next && rolls == 2, "all three native dice per roll and opt-out must stay exact");
}

class StructuredDamagePulseProbe : public CEffect {
  public:
    std::shared_ptr<CDamage> damage;
    void onEffect() override { hurtVictim(damage); }
};

void testNativeDamagePacketAndEffectCasterDoNotInferHitsFromHp() {
    auto game = load_empty_game();
    auto map = game->getMap();
    auto selected = add_test_creature(game, "unitSelectedOpponent");
    auto caster = add_test_creature(game, "unitActualEffectCaster", 2, 0);
    auto victim = add_test_creature(game, "unitPacketVictim", 1, 0);
    victim->getBaseStats()->setBlock(100);
    auto damage = std::make_shared<CDamage>();
    damage->setNormal(7);
    damage->setFire(3);
    int packets = 0;
    std::shared_ptr<CCreature> expected_cause = selected;
    std::shared_ptr<StructuredDamagePulseProbe> expected_effect;
    const auto runPacket = [&](const std::shared_ptr<CCreature> &cause) {
        CNativeCombatScope operation(game);
        victim->hurtFrom(cause, damage);
        operation.finish();
    };
    map->getEventHandler()->registerTrigger(
        std::make_shared<CCustomTrigger>(victim->getName(), "onCombatPacket", [&](auto object, auto event) {
            auto caused = std::dynamic_pointer_cast<CGameEventCaused>(event);
            expect_true(object == victim && caused && caused->getCause() == expected_cause,
                        "packet cause must come from its explicit producer, including an effect's actual caster");
            expect_true(event->getNumericProperty("combatNormal") == 7 &&
                            event->getNumericProperty("combatFire") == 3 &&
                            event->getNumericProperty("combatHpBefore") == event->getNumericProperty("combatHpAfter"),
                        "one fully blocked five-channel packet remains observable without fabricating HP loss");
            expect_true(event->getObjectProperty("combatProducer") == expected_effect,
                        "an effect packet retains the actual effect instance without a selected-opponent guess");
            ++packets;
        }));
    map->setBoolProperty("nativeCombatFacts", true);
    srand(20261104u);
    victim->hurt(damage);
    const int legacy_next = rand();
    srand(20261104u);
    runPacket(selected);
    expect_true(rand() == legacy_next && packets == 1,
                "a structured packet preserves all five legacy block dice and emits exactly once");
    victim->getBaseStats()->setBlock(0);
    victim->getBaseStats()->setNormalResist(100);
    victim->getBaseStats()->setFireResist(100);
    runPacket(selected);
    expect_true(packets == 2, "a fully resisted packet remains distinct from an attack miss");
    expected_cause = caster;
    expected_effect = std::make_shared<StructuredDamagePulseProbe>();
    expected_effect->damage = damage;
    expected_effect->setGame(game);
    expected_effect->setCaster(caster);
    expected_effect->setVictim(victim);
    expected_effect->setDuration(1);
    expected_effect->apply(victim);
    expect_true(packets == 3, "an effect packet emits once with its actual caster, without a new cast attempt");

    auto stale = caster;
    map->removeObject(stale);
    auto replacement = add_test_creature(game, stale->getName(), 2, 0);
    expected_effect->setDuration(1);
    expected_effect->apply(victim);
    expect_true(packets == 3, "a replaced caster cannot be attributed to a new same-name actor");
    auto other_game = load_empty_game();
    auto foreign = add_test_creature(other_game, "unitForeignCause");
    runPacket(foreign);
    expect_true(packets == 3, "a foreign game cannot acquire a native cause observation in this map");
    int stale_rolls = 0;
    map->getEventHandler()->registerTrigger(
        std::make_shared<CCustomTrigger>(victim->getName(), "onCombatRoll", [&](auto, auto) { ++stale_rolls; }));
    CNativeCombatScope superseded(game);
    CNativeCombatFacts captured(selected, victim);
    game->getContext()->advanceTransitionGeneration();
    captured.roll(true, 0);
    superseded.finish();
    map->setBoolProperty("nativeCombatFacts", false);
    runPacket(selected);
    expect_true(packets == 3 && stale_rolls == 0, "transitioned captures and disabled maps dispatch no facts");
}

class NativePhysicalSwingProbe : public CInteraction {
  public:
    void performAction(std::shared_ptr<CCreature> first, std::shared_ptr<CCreature> second) override {
        const int damage = first->getDmgFor(second);
        if (damage) {
            second->hurtFrom(first, damage);
            auto weapon = first->getWeapon();
            if (weapon && weapon->getInteraction()) {
                weapon->getInteraction()->onAction(first, second);
            }
        }
    }
};

class NativeArmorPacketProbe : public CInteraction {
  public:
    int performed = 0;
    void performAction(std::shared_ptr<CCreature> first, std::shared_ptr<CCreature> second) override {
        ++performed;
        second->hurtFrom(first, 1);
    }
};

void testNativeUseActionRetainsMissAndReversedArmorCause() {
    auto game = load_empty_game();
    auto map = game->getMap();
    auto attacker = add_test_creature(game, "unitMissedNpcAttacker");
    auto ally = add_test_creature(game, "unitArmoredAlly", 1, 0);
    auto swing = std::make_shared<NativePhysicalSwingProbe>();
    swing->setGame(game);
    swing->setOffensive(true);
    attacker->addAction(swing);
    auto response = std::make_shared<NativeArmorPacketProbe>();
    response->setGame(game);
    response->setOffensive(true);
    auto armor = std::make_shared<CArmor>();
    armor->setGame(game);
    armor->setName("unitCausalArmor");
    armor->setInteraction(response);
    ally->addItem(armor);
    ally->setArmor(armor);
    map->setBoolProperty("nativeCombatFacts", true);
    std::vector<std::string> observed;
    bool connected = false;
    for (const auto &target : {attacker, ally}) {
        for (const auto &kind : {"onCombatAttempt", "onCombatRoll", "onCombatPacket"}) {
            map->getEventHandler()->registerTrigger(
                std::make_shared<CCustomTrigger>(target->getName(), kind, [&](auto object, auto event) {
                    auto caused = std::dynamic_pointer_cast<CGameEventCaused>(event);
                    expect_true(caused != nullptr, "every native fact has its actual explicit cause");
                    observed.push_back(event->getStringProperty("combatKind") + ":" + caused->getCause()->getName() +
                                       ":" + object->getName());
                    if (event->getStringProperty("combatKind") == "onCombatRoll") {
                        expect_true(event->getBoolProperty("combatConnected") == connected,
                                    "a genuine useAction preserves both a miss and a zero-damage hit");
                    }
                }));
        }
    }
    const std::vector<std::string> expected{
        "onCombatAttempt:unitMissedNpcAttacker:unitArmoredAlly",
        "onCombatRoll:unitMissedNpcAttacker:unitArmoredAlly",
        "onCombatAttempt:unitArmoredAlly:unitMissedNpcAttacker",
        "onCombatPacket:unitArmoredAlly:unitMissedNpcAttacker",
    };
    auto stats = attacker->getBaseStats();
    stats->setAttack(0);
    stats->setDamage(0);
    stats->setDmgMin(0);
    stats->setDmgMax(0);
    stats->setHit(0);
    attacker->useAction(swing, ally);
    expect_true(observed == expected, "a miss cannot hide the attempt or reverse the armor proc aggressor");
    observed.clear();
    connected = true;
    stats->setHit(100);
    attacker->useAction(swing, ally);
    expect_true(observed == expected, "a zero-damage hit retains its actual roll without inventing a damage packet");
}
