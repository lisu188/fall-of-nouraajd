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

class NativeOneDamagePulseProbe : public CEffect {
  public:
    int ticks = 0;
    void onEffect() override {
        ++ticks;
        hurtVictim(1);
    }
};

void testNativeEffectRunnerOptOutRetainsBothTicks() {
    auto game = load_empty_game();
    auto victim = add_test_creature(game, "unitLegacyEffectReceiver");
    auto caster = add_test_creature(game, "unitLegacyEffectCaster", 1, 0);
    int callbacks = 0;
    auto hook = std::make_shared<CCustomTrigger>(victim->getName(), "onCombatPacket", [&](auto, auto) { ++callbacks; });
    hook->setName("unitLegacyEffectObserver");
    game->getMap()->getEventHandler()->registerTrigger(hook);
    std::vector<std::shared_ptr<NativeOneDamagePulseProbe>> pulses;
    for (const auto &name : {"unitLegacyPulseA", "unitLegacyPulseB"}) {
        auto effect = std::make_shared<NativeOneDamagePulseProbe>();
        effect->setGame(game);
        effect->setName(name);
        effect->setTypeId(name);
        effect->setCumulative(true);
        effect->setDuration(1);
        effect->setCaster(caster);
        effect->setVictim(victim);
        victim->addEffect(effect);
        pulses.push_back(effect);
    }
    CFightHandler::applyEffects(victim);
    expect_true(victim->getEffects().size() == 2 && victim->getHp() == 8 && pulses[0]->ticks == 1 &&
                    pulses[1]->ticks == 1 && callbacks == 0,
                "default opt-out applies both original one-point ticks without combat-fact callbacks");
}

void testNativeEffectRunnerStopsAfterFirstPulseObserverInvalidatesReceiver() {
    for (bool real_fight : {false, true}) {
        for (const auto &mode : {"removal", "replacement", "transfer", "generation", "shutdown"}) {
            auto game = load_empty_game();
            auto foreign = load_empty_game();
            auto map = game->getMap();
            auto victim = add_test_creature(game, "unitEffectRunnerVictim");
            auto caster = add_test_creature(game, "unitEffectRunnerCaster", 1, 0);
            auto controller = std::make_shared<AllocationOrderCancellationProbe>();
            victim->setFightController(controller);
            victim->getBaseStats()->setAgility(100);
            victim->getBaseStats()->setBlock(0);
            victim->getBaseStats()->setNormalResist(0);
            auto loot = add_unit_loot(game, victim, "unitEffectRunnerOwnedLoot");
            const int caster_exp = caster->getExp();
            const int caster_gold = caster->getGold();
            const int victim_exp = victim->getExp();
            const int victim_gold = victim->getGold();
            std::vector<std::shared_ptr<NativeOneDamagePulseProbe>> pulses;
            for (const auto &name : {"unitEffectRunnerPulseA", "unitEffectRunnerPulseB"}) {
                auto effect = std::make_shared<NativeOneDamagePulseProbe>();
                effect->setGame(game);
                effect->setName(name);
                effect->setTypeId(name);
                effect->setCumulative(true);
                effect->setDuration(1);
                effect->setCaster(caster);
                effect->setVictim(victim);
                victim->addEffect(effect);
                pulses.push_back(effect);
            }
            expect_true(victim->getEffects().size() == 2,
                        "the real runner must receive two distinct cumulative pulses");
            int callbacks = 0;
            std::shared_ptr<CCreature> replacement;
            auto hook =
                std::make_shared<CCustomTrigger>(victim->getName(), "onCombatPacket", [&](auto object, auto event) {
                    ++callbacks;
                    auto caused = std::dynamic_pointer_cast<CGameEventCaused>(event);
                    expect_true(object == victim && caused && caused->getCause() == caster && victim->getHp() == 9 &&
                                    pulses[0]->ticks == 1 && pulses[1]->ticks == 0,
                                "the first real pulse retains its actual caster and publishes before the second pulse");
                    if (std::string(mode) == "generation") {
                        game->getContext()->advanceTransitionGeneration();
                    } else if (std::string(mode) == "shutdown") {
                        game->getContext()->shutdown();
                    } else {
                        map->removeObject(victim);
                        if (std::string(mode) == "replacement") {
                            replacement = add_test_creature(game, victim->getName());
                        } else if (std::string(mode) == "transfer") {
                            victim->setGame(foreign);
                            foreign->getMap()->addObject(victim);
                        }
                    }
                });
            hook->setName("unitEffectRunnerInvalidator");
            map->getEventHandler()->registerTrigger(hook);
            map->setBoolProperty("nativeCombatFacts", true);
            if (real_fight) {
                const auto result = CFightHandler::fightManyResult(victim, {caster});
                expect_true(result.outcome == CFightOutcome::Cancelled && controller->controls == 0,
                            "an interrupted real fight effect phase cannot reach an old controller or defeat branch");
            } else {
                CFightHandler::applyEffects(victim);
            }
            expect_true(callbacks == 1 && victim->getHp() == 9 && pulses[0]->ticks == 1 && pulses[1]->ticks == 0 &&
                            pulses[0]->getTimeLeft() == 0 && pulses[1]->getTimeLeft() == 1,
                        "receiver invalidation after pulse one must leave HP9 and the second old pulse untouched");
            expect_true(!replacement || replacement->getHp() == 10,
                        "a same-name replacement must never receive the old receiver's second pulse");
            expect_true(caster->getExp() == caster_exp && caster->getGold() == caster_gold &&
                            victim->getExp() == victim_exp && victim->getGold() == victim_gold &&
                            caster->countItems("unitEffectRunnerOwnedLoot") == 0 && victim->getItems().count(loot) == 1,
                        "interruption grants no defeat XP, gold or loot to any actor");
        }
    }
}

void testNativePublishingNestedActionsAreNonrecursiveBoundedAndRecoverable() {
    auto game = load_empty_game();
    auto map = game->getMap();
    auto attacker = add_test_creature(game, "unitPublishingAttacker");
    auto victim = add_test_creature(game, "unitPublishingVictim", 1, 0);
    auto action = std::make_shared<CommittedOffensiveProbe>();
    action->setGame(game);
    action->setOffensive(true);
    int callbacks = 0;
    int depth = 0;
    int maximum_depth = 0;
    bool chain = true;
    bool unbounded_chain = false;
    auto hook = std::make_shared<CCustomTrigger>(victim->getName(), "onCombatAttempt", [&](auto, auto) {
        ++depth;
        maximum_depth = std::max(maximum_depth, depth);
        ++callbacks;
        if (chain && (unbounded_chain || callbacks == 1)) {
            const int at_entry = callbacks;
            action->onAction(attacker, victim);
            expect_true(callbacks == at_entry, "a callback-created real action cannot recursively flush observers");
        }
        --depth;
    });
    hook->setName("unitPublishingNestedAction");
    map->getEventHandler()->registerTrigger(hook);
    map->setBoolProperty("nativeCombatFacts", true);
    action->onAction(attacker, victim);
    expect_true(callbacks == 2 && action->performed == 2 && maximum_depth == 1,
                "one nested real action appends and drains one fact after its parent callback returns");
    callbacks = 0;
    action->performed = 0;
    unbounded_chain = true;
    bool refused = false;
    try {
        action->onAction(attacker, victim);
    } catch (const std::runtime_error &error) {
        refused = std::string(error.what()).find("fixed work budget") != std::string::npos;
    }
    expect_true(refused && callbacks == 128 && action->performed == 129 && maximum_depth == 1 && depth == 0,
                "publishing-time action chains stop at the fixed fact cap without recursive callback growth");
    chain = false;
    action->onAction(attacker, victim);
    expect_true(callbacks == 129 && action->performed == 130, "overflow during draining releases a fresh operation");
}

void testNativeEffectRunnerCancelsOpponentAndAllyActionTails() {
    for (bool allied : {false, true}) {
        auto game = load_empty_game();
        auto map = game->getMap();
        std::shared_ptr<CCreature> hero = allied ? std::static_pointer_cast<CCreature>(add_test_player(game))
                                                 : add_test_creature(game, "unitRunnerHero");
        auto victim = add_test_creature(game, "unitRunnerSideVictim", 1, 0);
        auto caster = add_test_creature(game, "unitRunnerSideCaster", 2, 0);
        hero->setAffiliation("unitRunnerHeroSide");
        victim->setAffiliation(allied ? "unitRunnerHeroSide" : "unitRunnerEnemySide");
        caster->setAffiliation("unitRunnerEnemySide");
        auto hero_control = std::make_shared<AllocationOrderCancellationProbe>();
        auto victim_control = std::make_shared<AllocationOrderCancellationProbe>();
        hero->setFightController(hero_control);
        victim->setFightController(victim_control);
        hero->getBaseStats()->setAgility(1);
        victim->getBaseStats()->setAgility(100);
        caster->getBaseStats()->setAgility(0);
        std::vector<std::shared_ptr<NativeOneDamagePulseProbe>> pulses;
        for (const auto &name : {"unitSidePulseA", "unitSidePulseB"}) {
            auto effect = std::make_shared<NativeOneDamagePulseProbe>();
            effect->setGame(game);
            effect->setTypeId(name);
            effect->setName(name);
            effect->setCumulative(true);
            effect->setDuration(1);
            effect->setVictim(victim);
            effect->setCaster(caster);
            victim->addEffect(effect);
            pulses.push_back(effect);
        }
        int callbacks = 0;
        auto hook = std::make_shared<CCustomTrigger>(victim->getName(), "onCombatPacket", [&](auto, auto) {
            ++callbacks;
            game->getContext()->advanceTransitionGeneration();
        });
        hook->setName("unitSideEffectInvalidator");
        map->getEventHandler()->registerTrigger(hook);
        map->setBoolProperty("nativeCombatFacts", true);
        const auto result = allied ? CFightHandler::fightManyWithAlliesResult(hero, {caster}, {victim})
                                   : CFightHandler::fightManyResult(hero, {victim});
        expect_true(result.outcome == CFightOutcome::Cancelled && callbacks == 1 && victim->getHp() == 9 &&
                        pulses[0]->ticks == 1 && pulses[1]->ticks == 0 && hero_control->controls == 0 &&
                        victim_control->controls == 0,
                    "both opponent and ally interrupted effect branches must cancel before any stale action tail");
    }
}

void testNativeCombatScopeDepthLimitAndThrowingObserverRecovery() {
    auto game = load_empty_game();
    auto map = game->getMap();
    auto attacker = add_test_creature(game, "unitDepthAttacker");
    auto victim = add_test_creature(game, "unitDepthVictim", 1, 0);
    map->setBoolProperty("nativeCombatFacts", true);
    int rolls = 0;
    auto roll_hook = std::make_shared<CCustomTrigger>(victim->getName(), "onCombatRoll", [&](auto, auto) { ++rolls; });
    roll_hook->setName("unitDepthRoll");
    map->getEventHandler()->registerTrigger(roll_hook);
    for (int limit : {32, 33}) {
        std::vector<std::unique_ptr<CNativeCombatScope>> scopes;
        for (int i = 0; i < limit; ++i)
            scopes.push_back(std::make_unique<CNativeCombatScope>(game));
        attacker->getDmgFor(victim);
        bool refused = false;
        for (auto it = scopes.rbegin(); it != scopes.rend(); ++it) {
            try {
                (*it)->finish();
            } catch (const std::runtime_error &error) {
                refused = std::string(error.what()).find("fixed work budget") != std::string::npos;
            }
        }
        expect_true(rolls == 1 && refused == (limit == 33),
                    "32 nested scopes accept one real roll; scope33 explicitly refuses its whole observation batch");
    }
    {
        CNativeCombatScope fresh(game);
        attacker->getDmgFor(victim);
        fresh.finish();
    }
    expect_true(rolls == 2, "scope overflow releases the context for a fresh valid roll");
    auto action = std::make_shared<CommittedOffensiveProbe>();
    action->setGame(game);
    action->setOffensive(true);
    bool should_throw = true;
    int callbacks = 0;
    for (int i = 0; i < 2; ++i) {
        auto hook = std::make_shared<CCustomTrigger>(victim->getName(), "onCombatAttempt", [&](auto, auto) {
            ++callbacks;
            if (should_throw)
                throw std::runtime_error("unit observer failure");
        });
        hook->setName("unitThrowingObserver_" + std::to_string(i));
        map->getEventHandler()->registerTrigger(hook);
    }
    bool propagated = false;
    try {
        action->onAction(attacker, victim);
    } catch (const std::runtime_error &error) {
        propagated = std::string(error.what()) == "unit observer failure";
    }
    expect_true(propagated && callbacks == 1 && action->performed == 1,
                "a throwing observer follows completed work and prevents all later listeners in that batch");
    should_throw = false;
    action->onAction(attacker, victim);
    expect_true(callbacks == 3 && action->performed == 2,
                "throwing delivery releases the batch for two fresh listeners");
}
