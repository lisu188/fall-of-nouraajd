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

class NativeEncounterPulseProbe : public CEffect {
  public:
    int ticks = 0;
    void onEffect() override {
        ++ticks;
        hurtVictim(1);
    }
};

class NativeEncounterPulseActionProbe : public CInteraction {
  public:
    std::shared_ptr<NativeEncounterPulseProbe> pulse;
    void performAction(std::shared_ptr<CCreature> first, std::shared_ptr<CCreature> second) override {
        pulse->setCaster(first);
        pulse->setVictim(second);
        pulse->setDuration(1);
        pulse->apply(second);
    }
};

class NativeEncounterUseActionProbe : public NoProgressFightController {
  public:
    std::shared_ptr<CInteraction> action;
    int controls = 0;
    bool control(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) override {
        ++controls;
        if (controls == 1) {
            me->useAction(action, opponent);
        }
        return true;
    }
    bool isCancelled(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override { return controls > 1; }
};

void runFactOnlyEncounterGenerationContinuationRegression() {
    for (bool lethal : {false, true}) {
        auto game = load_empty_game();
        auto map = game->getMap();
        auto attacker = add_test_creature(game, "unitFactOnlyAttacker");
        auto opponent = add_test_creature(game, "unitFactOnlyOpponent", 1, 0);
        attacker->getBaseStats()->setAgility(100);
        attacker->getBaseStats()->setBlock(0);
        opponent->getBaseStats()->setBlock(0);
        opponent->getBaseStats()->setNormalResist(0);
        opponent->setHp(lethal ? 1 : 10);
        auto pulse = std::make_shared<NativeEncounterPulseProbe>();
        pulse->setGame(game);
        auto action = std::make_shared<NativeEncounterPulseActionProbe>();
        action->setGame(game);
        action->setName("unitFactOnlyPulseAction");
        action->setManaCost(3);
        action->setOffensive(true);
        action->pulse = pulse;
        attacker->addAction(action);
        attacker->setMana(3);
        auto attacker_control = std::make_shared<NativeEncounterUseActionProbe>();
        attacker_control->action = action;
        attacker->setFightController(attacker_control);
        auto reply = std::make_shared<NativeArmorPacketProbe>();
        reply->setGame(game);
        reply->setName("unitFactOnlyReply");
        opponent->addAction(reply);
        auto opponent_control = std::make_shared<NativeEncounterUseActionProbe>();
        opponent_control->action = reply;
        opponent->setFightController(opponent_control);
        auto loot = add_unit_loot(game, opponent, "unitFactOnlyOwnedLoot");
        const int attacker_exp = attacker->getExp();
        const int attacker_gold = attacker->getGold();
        int callbacks = 0;
        const auto generation = game->getContext()->captureTransitionGeneration();
        auto hook =
            std::make_shared<CCustomTrigger>(opponent->getName(), "onCombatPacket", [&](auto object, auto event) {
                auto caused = std::dynamic_pointer_cast<CGameEventCaused>(event);
                expect_true(object == opponent && caused && caused->getCause() == attacker &&
                                event->getObjectProperty("combatProducer") == pulse && pulse->ticks == 1 &&
                                pulse->getTimeLeft() == 0 && attacker->getMana() == 0,
                            "the actual completed effect pulse must publish its real producer and committed payment");
                ++callbacks;
                game->getContext()->advanceTransitionGeneration();
            });
        hook->setName("unitFactOnlyGenerationObserver");
        map->getEventHandler()->registerTrigger(hook);
        map->setBoolProperty("nativeCombatFacts", true);
        expect_true(!map->getBoolProperty("guardNativeEncounterSaves") &&
                        !map->getBoolProperty("plugin_cityAlliedCombat"),
                    "the regression must opt into facts without native save admission or configured allies");
        const auto result = CFightHandler::fightManyResult(attacker, {opponent});
        expect_true(result.outcome == CFightOutcome::Cancelled && callbacks == 1 &&
                        !game->getContext()->isTransitionGenerationCurrent(generation) &&
                        attacker_control->controls == 1 && opponent_control->controls == 0 && attacker->getHp() == 10 &&
                        attacker->getMana() == 0 && opponent->getHp() == (lethal ? 0 : 9),
                    "fact-only encounter invalidation must retain committed damage and stop later controller work");
        expect_true(map->getObjectByName(opponent->getName()) == opponent && opponent->getItems().count(loot) == 1 &&
                        attacker->countItems("unitFactOnlyOwnedLoot") == 0 && attacker->getExp() == attacker_exp &&
                        attacker->getGold() == attacker_gold,
                    "stale encounter continuation must not remove a dead receiver or settle its rewards");
    }
}

void runEffectObserverSelectedOpponentContinuationRegression() {
    for (bool save_guard : {false, true}) {
        for (const auto &mode : {"removal", "transfer", "replacement"}) {
            auto game = load_empty_game();
            auto foreign = load_empty_game();
            auto map = game->getMap();
            auto attacker = add_test_creature(game, "unitSelectedTargetAttacker");
            auto selected = add_test_creature(game, "unitSelectedTargetCaster", 1, 0);
            attacker->getBaseStats()->setAgility(100);
            attacker->getBaseStats()->setBlock(0);
            attacker->getBaseStats()->setNormalResist(0);
            selected->getBaseStats()->setBlock(0);
            auto pulse = std::make_shared<NativeEncounterPulseProbe>();
            pulse->setGame(game);
            pulse->setName("unitSelectedTargetPulse");
            pulse->setTypeId("unitSelectedTargetPulse");
            pulse->setCumulative(true);
            pulse->setDuration(1);
            pulse->setCaster(selected);
            pulse->setVictim(attacker);
            attacker->addEffect(pulse);
            auto action = std::make_shared<NativeArmorPacketProbe>();
            action->setGame(game);
            action->setName("unitSelectedTargetAttack");
            attacker->addAction(action);
            auto controller = std::make_shared<NativeEncounterUseActionProbe>();
            controller->action = action;
            attacker->setFightController(controller);
            auto loot = add_unit_loot(game, selected, "unitSelectedTargetOwnedLoot");
            const int exp = attacker->getExp();
            const int gold = attacker->getGold();
            const auto generation = game->getContext()->captureTransitionGeneration();
            int callbacks = 0;
            std::shared_ptr<CCreature> replacement;
            auto hook =
                std::make_shared<CCustomTrigger>(attacker->getName(), "onCombatPacket", [&](auto object, auto event) {
                    auto caused = std::dynamic_pointer_cast<CGameEventCaused>(event);
                    expect_true(object == attacker && caused && caused->getCause() == selected &&
                                    event->getObjectProperty("combatProducer") == pulse && attacker->getHp() == 9,
                                "the original attacker effect must publish its actual selected-opponent caster");
                    ++callbacks;
                    map->removeObject(selected);
                    if (std::string(mode) == "transfer") {
                        selected->setGame(foreign);
                        foreign->getMap()->addObject(selected);
                    } else if (std::string(mode) == "replacement") {
                        replacement = add_test_creature(game, selected->getName(), 1, 0);
                    }
                });
            hook->setName("unitSelectedTargetInvalidator");
            map->getEventHandler()->registerTrigger(hook);
            map->setBoolProperty("guardNativeEncounterSaves", save_guard);
            map->setBoolProperty("nativeCombatFacts", true);
            const auto result = CFightHandler::fightManyResult(attacker, {selected});
            expect_true(result.outcome == CFightOutcome::Cancelled && callbacks == 1 && controller->controls == 0 &&
                            action->performed == 0 && pulse->ticks == 1 && pulse->getTimeLeft() == 0 &&
                            attacker->getHp() == 9 && selected->getHp() == 10 &&
                            map->getObjectByName(attacker->getName()) == attacker &&
                            game->getContext()->isTransitionGenerationCurrent(generation),
                        "a removed, transferred or replaced selected target cannot reach the next attack controller");
            expect_true(!replacement || replacement->getHp() == 10,
                        "the same-name replacement must remain outside the old encounter");
            expect_true(attacker->getExp() == exp && attacker->getGold() == gold &&
                            selected->getItems().count(loot) == 1 &&
                            attacker->countItems("unitSelectedTargetOwnedLoot") == 0,
                        "selected-target invalidation cannot grant stale defeat rewards");
        }
    }
}

class NativeContinuationTargetProbe : public NativeEncounterUseActionProbe {
  public:
    std::shared_ptr<CCreature> preferred;
    std::shared_ptr<CCreature> selectOpponent(std::shared_ptr<CCreature>,
                                              const std::vector<std::shared_ptr<CCreature>> &,
                                              std::shared_ptr<CCreature>) override {
        return preferred;
    }
};

void invalidateNativeContinuationParticipant(const std::string &mode, const std::shared_ptr<CGame> &game,
                                             const std::shared_ptr<CGame> &foreign,
                                             const std::shared_ptr<CCreature> &participant,
                                             std::shared_ptr<CCreature> &replacement) {
    auto map = game->getMap();
    const auto name = participant->getName();
    const auto coords = participant->getCoords();
    const int hp = participant->getHp();
    const int mana = participant->getMana();
    const auto player = std::dynamic_pointer_cast<CPlayer>(participant);
    if (player) {
        // onDestroy respawns assigned players; detach exercises actual registration loss without death.
        const auto assigned = map->getAssignedPlayer();
        const auto detached = map->detachPlayer();
        expect_true(assigned == player && detached == player,
                    "the invalidation fixture must detach the actual assigned player");
        expect_true(map->getAssignedPlayer() == nullptr,
                    "detaching the invalidated player must clear the old map assignment");
    } else {
        map->removeObject(participant);
    }
    expect_true(map->getObjectByName(name) == nullptr,
                "the invalidation fixture must remove the original registry entry before transfer or replacement");
    if (mode == "transfer") {
        participant->setGame(foreign);
        if (player) {
            foreign->getMap()->attachPlayer(player, coords);
        } else {
            foreign->getMap()->addObject(participant);
        }
        expect_true(participant->getGame() == foreign && participant->getMap() == foreign->getMap() &&
                        foreign->getMap()->getObjectByName(name) == participant &&
                        (!player || foreign->getMap()->getAssignedPlayer() == player),
                    "transfer must register the original participant with its actual foreign owner");
    } else if (mode == "replacement") {
        replacement = player ? std::static_pointer_cast<CCreature>(add_test_player(game))
                             : add_test_creature(game, name, coords.x, coords.y);
        replacement->relocateWithoutMoveHooks(coords);
        expect_true(replacement != participant && replacement->getName() == name &&
                        map->getObjectByName(name) == replacement && replacement->getGame() == game &&
                        replacement->getMap() == map && (!player || map->getAssignedPlayer() == replacement),
                    "replacement must register a distinct original-name participant and the actual player assignment");
    }
    expect_true(map->getObjectByName(name) != participant && participant->getHp() == hp &&
                    participant->getMana() == mana,
                "actual invalidation must preserve committed HP and mana without respawn or stale registration");
}

void runReversedEffectParticipantContinuationRegression() {
    for (bool save_guard : {false, true}) {
        for (int role : {0, 1, 2}) {
            for (const auto &mode : {"removal", "transfer", "replacement"}) {
                auto game = load_empty_game();
                auto foreign = load_empty_game();
                auto map = game->getMap();
                std::shared_ptr<CCreature> hero = add_test_player(game);
                auto opponent = add_test_creature(game, "unitReverseOpponent", 1, 0);
                auto ally = role == 0 ? std::shared_ptr<CCreature>() : add_test_creature(game, "unitReverseAlly", 2, 0);
                hero->setAffiliation("unitReverseHeroSide");
                opponent->setAffiliation("unitReverseEnemySide");
                if (ally) {
                    ally->setAffiliation("unitReverseHeroSide");
                }
                auto receiver = role == 2 ? ally : opponent;
                auto invalidated = role == 1 ? ally : hero;
                auto caster = role == 2 ? opponent : invalidated;
                std::vector<std::shared_ptr<CCreature>> actors{hero, opponent};
                if (ally) {
                    actors.push_back(ally);
                }
                std::vector<int> experience;
                std::vector<int> gold;
                for (const auto &actor : actors) {
                    actor->setHp(10);
                    actor->getBaseStats()->setAgility(actor == receiver ? 100 : 0);
                    actor->getBaseStats()->setBlock(0);
                    actor->getBaseStats()->setNormalResist(0);
                    actor->setFightController(std::make_shared<NoProgressFightController>());
                    experience.push_back(actor->getExp());
                    gold.push_back(actor->getGold());
                }
                auto pulse = std::make_shared<NativeEncounterPulseProbe>();
                pulse->setGame(game);
                pulse->setName("unitReversePulse");
                pulse->setTypeId("unitReversePulse");
                pulse->setCumulative(true);
                pulse->setDuration(1);
                pulse->setCaster(caster);
                pulse->setVictim(receiver);
                receiver->addEffect(pulse);
                auto action = std::make_shared<NativeArmorPacketProbe>();
                action->setGame(game);
                action->setName("unitReverseStaleAction");
                receiver->addAction(action);
                auto controller = std::make_shared<NativeContinuationTargetProbe>();
                controller->action = action;
                controller->preferred = role == 2 ? opponent : invalidated;
                receiver->setFightController(controller);
                auto loot = add_unit_loot(game, invalidated, "unitReverseOwnedLoot");
                const auto generation = game->getContext()->captureTransitionGeneration();
                int callbacks = 0;
                std::shared_ptr<CCreature> replacement;
                auto hook = std::make_shared<CCustomTrigger>(
                    receiver->getName(), "onCombatPacket", [&](auto object, auto event) {
                        auto caused = std::dynamic_pointer_cast<CGameEventCaused>(event);
                        expect_true(object == receiver && caused && caused->getCause() == caster &&
                                        event->getObjectProperty("combatProducer") == pulse && receiver->getHp() == 9,
                                    "the completed reverse-role pulse must expose its real receiver and caster");
                        ++callbacks;
                        invalidateNativeContinuationParticipant(mode, game, foreign, invalidated, replacement);
                    });
                hook->setName("unitReverseParticipantObserver");
                map->getEventHandler()->registerTrigger(hook);
                map->setBoolProperty("guardNativeEncounterSaves", save_guard);
                map->setBoolProperty("nativeCombatFacts", true);
                const auto result = ally ? CFightHandler::fightManyWithAlliesResult(hero, {opponent}, {ally})
                                         : CFightHandler::fightManyResult(hero, {opponent});
                expect_true(result.outcome == CFightOutcome::Cancelled && callbacks == 1 && controller->controls == 0 &&
                                action->performed == 0 && pulse->ticks == 1 && pulse->getTimeLeft() == 0 &&
                                receiver->getHp() == 9 && invalidated->getHp() == 10 &&
                                game->getContext()->isTransitionGenerationCurrent(generation),
                            "opponent hero/ally targets and ally hero anchors cannot continue after effect removal");
                expect_true(!replacement || replacement->getHp() == 10,
                            "a same-name replacement cannot receive an old participant's action");
                expect_true(invalidated->getItems().count(loot) == 1,
                            "effect observer invalidation must retain the original owned loot");
                for (std::size_t index = 0; index < actors.size(); ++index) {
                    expect_true(actors[index]->getExp() == experience[index] && actors[index]->getGold() == gold[index],
                                "an invalid effect continuation cannot settle any participant's rewards");
                }
            }
        }
    }
}

void runActionObserverParticipantRegistrationRegression() {
    for (bool save_guard : {false, true}) {
        for (int role : {0, 1, 2}) {
            for (int changed_role : {0, 1, 2}) {
                if (role == 0 && changed_role == 2) {
                    continue;
                }
                for (const auto &mode : {"removal", "transfer", "replacement"}) {
                    auto game = load_empty_game();
                    auto foreign = load_empty_game();
                    auto map = game->getMap();
                    std::shared_ptr<CCreature> hero = add_test_player(game);
                    auto opponent = add_test_creature(game, "unitActionRegistrationOpponent", 1, 0);
                    auto ally = role == 0 ? std::shared_ptr<CCreature>()
                                          : add_test_creature(game, "unitActionRegistrationAlly", 2, 0);
                    hero->setAffiliation("unitActionRegistrationHeroSide");
                    opponent->setAffiliation("unitActionRegistrationEnemySide");
                    if (ally) {
                        ally->setAffiliation("unitActionRegistrationHeroSide");
                    }
                    auto actor = role == 0 ? hero : (role == 1 ? ally : opponent);
                    auto target = role == 2 ? ally : opponent;
                    auto invalidated = changed_role == 0 ? actor : (changed_role == 1 ? target : hero);
                    std::vector<std::shared_ptr<CCreature>> actors{hero, opponent};
                    if (ally) {
                        actors.push_back(ally);
                    }
                    std::vector<int> experience;
                    std::vector<int> gold;
                    for (const auto &participant : actors) {
                        participant->setHp(10);
                        participant->getBaseStats()->setAgility(participant == actor ? 100 : 0);
                        participant->getBaseStats()->setBlock(0);
                        participant->getBaseStats()->setNormalResist(0);
                        participant->setFightController(std::make_shared<NoProgressFightController>());
                        experience.push_back(participant->getExp());
                        gold.push_back(participant->getGold());
                    }
                    auto action = std::make_shared<NativeArmorPacketProbe>();
                    action->setGame(game);
                    action->setName("unitActionRegistrationCommittedAction");
                    action->setManaCost(3);
                    action->setOffensive(true);
                    actor->setMana(3);
                    actor->addAction(action);
                    auto controller = std::make_shared<NativeContinuationTargetProbe>();
                    controller->action = action;
                    controller->preferred = target;
                    actor->setFightController(controller);
                    auto loot = add_unit_loot(game, invalidated, "unitActionRegistrationOwnedLoot");
                    const auto generation = game->getContext()->captureTransitionGeneration();
                    int callbacks = 0;
                    std::shared_ptr<CCreature> replacement;
                    auto hook = std::make_shared<CCustomTrigger>(
                        target->getName(), "onCombatPacket", [&](auto object, auto event) {
                            auto caused = std::dynamic_pointer_cast<CGameEventCaused>(event);
                            expect_true(object == target && caused && caused->getCause() == actor &&
                                            action->performed == 1 && actor->getMana() == 0 && target->getHp() == 9,
                                        "action registration changes must follow real committed damage and payment");
                            ++callbacks;
                            invalidateNativeContinuationParticipant(mode, game, foreign, invalidated, replacement);
                        });
                    hook->setName("unitActionRegistrationObserver");
                    map->getEventHandler()->registerTrigger(hook);
                    map->setBoolProperty("guardNativeEncounterSaves", save_guard);
                    map->setBoolProperty("nativeCombatFacts", true);
                    const auto result = ally ? CFightHandler::fightManyWithAlliesResult(hero, {opponent}, {ally})
                                             : CFightHandler::fightManyResult(hero, {opponent});
                    expect_true(result.outcome == CFightOutcome::Cancelled && callbacks == 1 &&
                                    controller->controls == 1 && action->performed == 1 && actor->getMana() == 0 &&
                                    target->getHp() == 9 && invalidated->getItems().count(loot) == 1 &&
                                    game->getContext()->isTransitionGenerationCurrent(generation),
                                "post-action actor, target or hero-anchor invalidation must stop stale settlement");
                    expect_true(!replacement || replacement->getHp() == 10,
                                "the replacement must not inherit committed damage from the old participant");
                    for (std::size_t index = 0; index < actors.size(); ++index) {
                        expect_true(actors[index]->getExp() == experience[index] &&
                                        actors[index]->getGold() == gold[index],
                                    "an invalid action continuation cannot settle any participant's rewards");
                    }
                }
            }
        }
    }
}

void runRegisteredLethalActionStillSettlesRegression() {
    int legacy_experience = 0;
    int legacy_gold = 0;
    for (bool enabled : {false, true}) {
        auto game = load_empty_game();
        auto map = game->getMap();
        std::shared_ptr<CCreature> hero = add_test_player(game);
        auto opponent = add_test_creature(game, "unitRegisteredLethalOpponent", 1, 0);
        hero->getBaseStats()->setAgility(100);
        hero->getBaseStats()->setBlock(0);
        opponent->getBaseStats()->setBlock(0);
        opponent->getBaseStats()->setNormalResist(0);
        hero->setHp(10);
        opponent->setHp(1);
        opponent->addGold(7);
        const int owned_gold = opponent->getGold();
        auto loot = add_unit_loot(game, opponent, "unitRegisteredLethalLoot");
        auto action = std::make_shared<NativeArmorPacketProbe>();
        action->setGame(game);
        action->setName("unitRegisteredLethalAction");
        hero->addAction(action);
        auto controller = std::make_shared<NativeEncounterUseActionProbe>();
        controller->action = action;
        hero->setFightController(controller);
        opponent->setFightController(std::make_shared<NoProgressFightController>());
        const int experience = hero->getExp();
        const int gold = hero->getGold();
        int callbacks = 0;
        auto hook = std::make_shared<CCustomTrigger>(opponent->getName(), "onCombatPacket", [&](auto, auto) {
            ++callbacks;
            expect_true(opponent->getHp() == 0 && map->getObjectByName(opponent->getName()) == opponent,
                        "lethal damage is committed while the victim is still the registered original instance");
        });
        hook->setName("unitRegisteredLethalObserver");
        map->getEventHandler()->registerTrigger(hook);
        map->setBoolProperty("plugin_cityFixedLoot", true);
        map->setBoolProperty("nativeCombatFacts", enabled);
        const auto result = CFightHandler::fightManyResult(hero, {opponent});
        expect_true(result.outcome == CFightOutcome::AttackerVictory && action->performed == 1 &&
                        controller->controls == 1 && callbacks == (enabled ? 1 : 0) &&
                        map->getObjectByName(opponent->getName()) == nullptr && hero->getItems().count(loot) == 1 &&
                        hero->getExp() > experience && hero->getGold() - gold == owned_gold,
                    "registered lethal targets must retain ordinary defeat, XP, owned-gold and item settlement");
        if (!enabled) {
            legacy_experience = hero->getExp() - experience;
            legacy_gold = hero->getGold() - gold;
        } else {
            expect_true(hero->getExp() - experience == legacy_experience && hero->getGold() - gold == legacy_gold,
                        "fact opt-in cannot change ordinary registered lethal reward deltas");
        }
    }
}

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
    runFactOnlyEncounterGenerationContinuationRegression();
    runEffectObserverSelectedOpponentContinuationRegression();
    runReversedEffectParticipantContinuationRegression();
    runActionObserverParticipantRegistrationRegression();
    runRegisteredLethalActionStillSettlesRegression();
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
