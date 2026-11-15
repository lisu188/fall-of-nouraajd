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

// This regression uses only APIs present on the pinned BEFORE source.
class CommittedOffensiveProbe : public CInteraction {
  public:
    int performed = 0;
    void performAction(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) override { ++performed; }
};

void testCommittedOffensiveInteractionRetainsActualAggressor() {
    auto game = load_empty_game();
    auto map = game->getMap();
    auto attacker = add_test_creature(game, "unitOffensiveNpc");
    auto victim = add_test_creature(game, "unitAlliedVictim", 1, 0);
    auto action = std::make_shared<CommittedOffensiveProbe>();
    action->setGame(game);
    action->setManaCost(3);
    action->setBoolProperty("offensive", true);
    int attempts = 0;
    map->getEventHandler()->registerTrigger(
        std::make_shared<CCustomTrigger>(victim->getName(), "onCombatAttempt", [&](auto object, auto event) {
            auto caused = std::dynamic_pointer_cast<CGameEventCaused>(event);
            expect_true(object == victim && caused && caused->getCause() == attacker,
                        "the committed native NPC attack must retain the actual allied target and aggressor");
            expect_true(attacker->getMana() == 0 && action->performed == 2 &&
                            event->getNumericProperty("combatManaAtCommit") == 0,
                        "capture retains paid mana while delivery follows the complete native interaction");
            ++attempts;
        }));
    attacker->setMana(3);
    action->onAction(attacker, victim); // Default opt-out must not dispatch.
    expect_true(attempts == 0 && action->performed == 1, "ordinary maps preserve the old interaction path");
    map->setBoolProperty("nativeCombatFacts", true);
    attacker->setMana(2);
    action->onAction(attacker, victim);
    expect_true(attempts == 0 && action->performed == 1 && attacker->getMana() == 2,
                "insufficient mana cannot commit an offensive attempt");
    attacker->setMana(3);
    action->onAction(attacker, victim);
    expect_true(attempts == 1 && action->performed == 2 && attacker->getMana() == 0,
                "one genuinely paid native interaction must deliver one attempt without requiring HP loss");
}
