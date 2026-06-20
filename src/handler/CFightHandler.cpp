/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025-2026  Andrzej Lis

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
#include "CFightHandler.h"
#include <algorithm>
#include <tuple>
#include <unordered_set>

#include "core/CController.h"
#include "core/CGame.h"
#include "core/CMap.h"
#include "core/CPlaytestTrace.h"
#include "core/CTags.h"
#include "object/CCreature.h"
#include "object/CEffect.h"

namespace {
using encounter_type = std::vector<std::shared_ptr<CCreature>>;
using effect_state_type = std::tuple<std::string, std::string, int>;
using creature_state_type = std::tuple<std::string, int, int, std::vector<effect_state_type>, std::size_t>;

struct effect_application_result {
    bool died = false;
    std::shared_ptr<CCreature> caster;
};

class FightControllerEndGuard {
  public:
    ~FightControllerEndGuard() { endAll(); }

    void start(const std::shared_ptr<CFightController> &controller, const std::shared_ptr<CCreature> &creature,
               const std::shared_ptr<CCreature> &opponent) {
        if (!controller) {
            return;
        }
        controller->start(creature, opponent);
        startedControllers.push_back({controller, creature, opponent, nullptr, false});
    }

    void start(const std::shared_ptr<CFightController> &controller, const std::shared_ptr<CCreature> &creature,
               const std::shared_ptr<CCreature> *opponent) {
        if (!controller) {
            return;
        }
        controller->start(creature, opponent ? *opponent : std::shared_ptr<CCreature>());
        startedControllers.push_back({controller, creature, std::shared_ptr<CCreature>(), opponent, false});
    }

    void endAll() {
        for (auto &started : startedControllers) {
            if (started.ended || !started.controller) {
                continue;
            }
            started.ended = true;
            started.controller->end(started.creature,
                                    started.currentOpponent ? *started.currentOpponent : started.startedOpponent);
        }
    }

  private:
    struct StartedController {
        std::shared_ptr<CFightController> controller;
        std::shared_ptr<CCreature> creature;
        std::shared_ptr<CCreature> startedOpponent;
        const std::shared_ptr<CCreature> *currentOpponent;
        bool ended;
    };

    std::vector<StartedController> startedControllers;
};

std::vector<effect_state_type> effect_state(const std::shared_ptr<CCreature> &creature) {
    std::vector<effect_state_type> state;
    if (!creature) {
        return state;
    }
    for (const auto &effect : creature->getEffects()) {
        if (!effect) {
            state.emplace_back("<null>", "", 0);
            continue;
        }
        auto type_id = effect->getTypeId();
        if (type_id.empty()) {
            type_id = effect->getType();
        }
        auto name = effect->getName();
        if (name.empty()) {
            name = effect->getLabel();
        }
        state.emplace_back(type_id, name, effect->getTimeLeft());
    }
    std::sort(state.begin(), state.end());
    return state;
}

creature_state_type creature_state(const std::shared_ptr<CCreature> &creature) {
    if (!creature) {
        return std::make_tuple(std::string(), 0, 0, std::vector<effect_state_type>(), std::size_t{0});
    }
    return std::make_tuple(creature->getName(), creature->getHp(), creature->getMana(), effect_state(creature),
                           creature->getInInventory().size());
}

auto encounter_state(const std::shared_ptr<CCreature> &attacker, const encounter_type &opponents) {
    std::vector<creature_state_type> state;
    state.push_back(creature_state(attacker));
    for (const auto &opponent : opponents) {
        state.push_back(creature_state(opponent));
    }
    return state;
}

bool is_registered_on_map(const std::shared_ptr<CMap> &map, const std::shared_ptr<CCreature> &creature) {
    return map && creature && creature->getMap() == map && map->getObjectByName(creature->getName()) == creature;
}

bool is_active_participant(const std::shared_ptr<CMap> &map, const std::shared_ptr<CCreature> &creature) {
    return creature && creature->isAlive() && is_registered_on_map(map, creature);
}

bool contains_participant(const encounter_type &participants, const std::shared_ptr<CCreature> &creature) {
    return std::find(participants.begin(), participants.end(), creature) != participants.end();
}

std::string combat_name(const std::shared_ptr<CCreature> &creature) {
    if (!creature) {
        return "Unknown";
    }
    const auto label = creature->getLabel();
    return label.empty() ? creature->getName() : label;
}

int initiative_score(const std::shared_ptr<CCreature> &creature) {
    if (!creature) {
        return 0;
    }
    return creature->getStats()->getAgility() * 2 + creature->getLevel();
}

encounter_type build_turn_order(const std::shared_ptr<CMap> &encounterMap, const std::shared_ptr<CCreature> &attacker,
                                const encounter_type &opponents) {
    encounter_type order;
    if (is_active_participant(encounterMap, attacker)) {
        order.push_back(attacker);
    }
    for (const auto &opponent : opponents) {
        if (is_active_participant(encounterMap, opponent)) {
            order.push_back(opponent);
        }
    }
    std::stable_sort(order.begin(), order.end(), [attacker](const auto &left, const auto &right) {
        if (left == right) {
            return false;
        }
        const auto leftScore = initiative_score(left);
        const auto rightScore = initiative_score(right);
        if (leftScore != rightScore) {
            return leftScore > rightScore;
        }
        if (left == attacker) {
            return true;
        }
        if (right == attacker) {
            return false;
        }
        return combat_name(left) < combat_name(right);
    });
    return order;
}

std::string format_turn_order(const encounter_type &turnOrder) {
    std::string text = "Initiative: ";
    bool first = true;
    for (const auto &creature : turnOrder) {
        if (!first) {
            text += " > ";
        }
        text += combat_name(creature);
        text += " (";
        text += vstd::str(initiative_score(creature));
        text += ")";
        first = false;
    }
    return text;
}

void update_combat_status(const std::shared_ptr<CMap> &encounterMap, const std::shared_ptr<CCreature> &attacker,
                          const encounter_type &opponents, const std::string &message, bool includeInitiative = true) {
    if (!encounterMap) {
        return;
    }
    auto status = message;
    if (includeInitiative) {
        const auto turnOrder = build_turn_order(encounterMap, attacker, opponents);
        if (!status.empty()) {
            status += "\n";
        }
        status += format_turn_order(turnOrder);
    }
    encounterMap->setStringProperty("combatStatus", status);
}

void clear_combat_status(const std::shared_ptr<CMap> &encounterMap) {
    if (encounterMap) {
        encounterMap->setStringProperty("combatStatus", "");
    }
}

encounter_type sanitize_opponents(const std::shared_ptr<CMap> &encounterMap, const std::shared_ptr<CCreature> &attacker,
                                  const encounter_type &opponents) {
    if (!is_active_participant(encounterMap, attacker)) {
        return {};
    }

    encounter_type living;
    std::unordered_set<const CCreature *> identities;
    for (const auto &candidate : opponents) {
        if (!candidate || candidate == attacker || !candidate->isAlive() ||
            !is_registered_on_map(encounterMap, candidate)) {
            continue;
        }
        if (identities.insert(candidate.get()).second) {
            living.push_back(candidate);
        }
    }
    std::sort(living.begin(), living.end(),
              [](const auto &left, const auto &right) { return left->getName() < right->getName(); });
    return living;
}

std::shared_ptr<CCreature> resolve_target(const std::shared_ptr<CMap> &encounterMap,
                                          const std::shared_ptr<CCreature> &attacker, const encounter_type &opponents,
                                          std::shared_ptr<CCreature> current) {
    auto controller = attacker->getFightController();
    if (!controller) {
        return opponents.empty() ? std::shared_ptr<CCreature>() : opponents.front();
    }
    controller->setOpponents(attacker, opponents);
    auto selected = controller->selectOpponent(attacker, opponents, current);
    if (is_active_participant(encounterMap, selected) && contains_participant(opponents, selected)) {
        return selected;
    }
    return opponents.empty() ? std::shared_ptr<CCreature>() : opponents.front();
}

bool is_reward_eligible_winner(const std::shared_ptr<CMap> &encounterMap, const std::shared_ptr<CCreature> &attacker,
                               const encounter_type &opponents, const std::shared_ptr<CCreature> &loser,
                               const std::shared_ptr<CCreature> &winner) {
    if (!is_active_participant(encounterMap, winner) || !loser || winner == loser) {
        return false;
    }
    const bool loser_is_attacker = loser == attacker;
    const bool loser_is_opponent = contains_participant(opponents, loser);
    const bool winner_is_attacker = winner == attacker;
    const bool winner_is_opponent = contains_participant(opponents, winner);
    if (loser_is_attacker) {
        return winner_is_opponent;
    }
    if (loser_is_opponent) {
        return winner_is_attacker;
    }
    return false;
}

bool resolve_defeat(const std::shared_ptr<CMap> &encounterMap, const std::shared_ptr<CCreature> &attacker,
                    const encounter_type &opponents, const std::shared_ptr<CCreature> &loser,
                    const std::shared_ptr<CCreature> &winner) {
    if (!loser || loser->isAlive() || !is_registered_on_map(encounterMap, loser)) {
        return false;
    }
    if (is_reward_eligible_winner(encounterMap, attacker, opponents, loser, winner)) {
        CFightHandler::defeatedCreature(winner, loser);
    } else {
        encounterMap->removeObject(loser);
    }
    return true;
}

bool remove_dead_opponents(const std::shared_ptr<CMap> &encounterMap, const std::shared_ptr<CCreature> &attacker,
                           encounter_type &opponents, const std::shared_ptr<CCreature> &winner) {
    bool changed = false;
    opponents.erase(std::remove_if(opponents.begin(), opponents.end(),
                                   [&](const auto &opponent) {
                                       if (!opponent || !is_registered_on_map(encounterMap, opponent)) {
                                           changed = true;
                                           return true;
                                       }
                                       if (opponent->isAlive()) {
                                           return false;
                                       }
                                       changed = true;
                                       resolve_defeat(encounterMap, attacker, opponents, opponent, winner);
                                       return true;
                                   }),
                    opponents.end());
    return changed;
}

void defeat_attacker(const std::shared_ptr<CMap> &encounterMap, const std::shared_ptr<CCreature> &attacker,
                     const encounter_type &opponents, const std::shared_ptr<CCreature> &winner) {
    resolve_defeat(encounterMap, attacker, opponents, attacker, winner);
}

effect_application_result apply_effects_with_result(const std::shared_ptr<CCreature> &cr) {
    effect_application_result result;
    if (!cr) {
        vstd::logger::warning("Skipping effect application for null creature");
        return result;
    }

    auto effects = cr->getEffects();
    for (const auto &effect : effects) {
        if (!effect) {
            vstd::logger::warning("Skipping null effect while expiring effects for", cr->to_string());
            continue;
        }
        if (effect->getTimeLeft() == 0) {
            vstd::logger::debug(cr->to_string(), "is now free from", effect->to_string());
            cr->removeEffect(effect);
        }
    }

    effects = cr->getEffects();
    for (const auto &effect : effects) {
        if (!effect) {
            vstd::logger::warning("Skipping null effect while applying effects for", cr->to_string());
            continue;
        }
        const bool was_alive = cr->isAlive();
        vstd::logger::debug(cr->to_string(), "suffers from", effect->to_string());
        effect->apply(cr);
        if (was_alive && !cr->isAlive()) {
            result.died = true;
            result.caster = effect->getCaster();
            break;
        }
    }
    return result;
}

std::string final_status_message(CFightOutcome outcome, const std::string &attackerName, int rounds = 0) {
    switch (outcome) {
    case CFightOutcome::AttackerVictory:
        return attackerName + " survives the encounter.";
    case CFightOutcome::AttackerDefeat:
        return attackerName + " is defeated.";
    case CFightOutcome::Stalled:
        if (rounds > 0) {
            return "Combat stalled after " + vstd::str(rounds) + " rounds without a victor.";
        }
        return "Combat stalled without a victor.";
    case CFightOutcome::Cancelled:
        return "Combat was cancelled before the encounter resolved.";
    case CFightOutcome::Invalid:
        return "";
    }
    return "";
}

CFightResult resolve_fight_many(std::shared_ptr<CCreature> attacker, const encounter_type &encounterOpponents) {
    CFightResult result;
    if (!attacker) {
        return result;
    }
    auto encounterMap = attacker->getMap();
    const auto attackerName = combat_name(attacker);
    if (!is_active_participant(encounterMap, attacker)) {
        clear_combat_status(encounterMap);
        return result;
    }

    auto opponents = sanitize_opponents(encounterMap, attacker, encounterOpponents);
    if (opponents.empty()) {
        clear_combat_status(encounterMap);
        return result;
    }

    auto allOpponents = opponents;
    auto current = opponents.front();
    auto attackerController = attacker->getFightController();
    if (!attackerController) {
        clear_combat_status(encounterMap);
        return result;
    }
    attackerController->setOpponents(attacker, opponents);
    FightControllerEndGuard controllerEndGuard;
    controllerEndGuard.start(attackerController, attacker, &current);
    for (const auto &opponent : allOpponents) {
        if (auto controller = opponent->getFightController()) {
            controllerEndGuard.start(controller, opponent, attacker);
        }
    }
    if (CPlaytestTrace::enabled()) {
        json fields = {
            {"attacker", CPlaytestTrace::objectRef(attacker)},
            {"opponents", CPlaytestTrace::objectRefs(allOpponents)},
        };
        CPlaytestTrace::addMapContext(fields, encounterMap);
        CPlaytestTrace::record("combat_started", fields);
    }

    int stale_turns = 0;
    for (int turn = 0; turn < 100 && stale_turns < 20 && result.outcome == CFightOutcome::Invalid &&
                       is_active_participant(encounterMap, attacker) && !opponents.empty();
         ++turn) {
        if (SDL_HasEvent(SDL_QUIT)) {
            result.outcome = CFightOutcome::Cancelled;
            result.survivor = attacker;
            result.opponent = current;
            break;
        }
        result.rounds = turn + 1;
        update_combat_status(encounterMap, attacker, opponents, "Combat round " + vstd::str(turn + 1) + " begins.");
        auto before = encounter_state(attacker, opponents);
        const auto turnOrder = build_turn_order(encounterMap, attacker, opponents);

        for (const auto &actor : turnOrder) {
            if (result.outcome != CFightOutcome::Invalid || !is_active_participant(encounterMap, attacker) ||
                opponents.empty()) {
                break;
            }

            if (actor == attacker) {
                current = resolve_target(encounterMap, attacker, opponents, current);
                update_combat_status(encounterMap, attacker, opponents,
                                     combat_name(attacker) + " acts against " + combat_name(current) + ".");

                auto effect_result = apply_effects_with_result(attacker);
                if (!attacker->isAlive()) {
                    result.outcome = CFightOutcome::AttackerDefeat;
                    result.survivor = effect_result.caster;
                    result.opponent = attacker;
                    defeat_attacker(encounterMap, attacker, opponents, effect_result.caster);
                    break;
                }

                if (!CTags::isTagPresent(attacker->getEffects(), CTag::Stun)) {
                    attackerController->control(attacker, current);
                    if (attackerController->isCancelled(attacker, current)) {
                        result.outcome = CFightOutcome::Cancelled;
                        result.survivor = attacker;
                        result.opponent = current;
                        break;
                    }
                    remove_dead_opponents(encounterMap, attacker, opponents, attacker);
                    if (!attacker->isAlive()) {
                        result.outcome = CFightOutcome::AttackerDefeat;
                        result.survivor = current;
                        result.opponent = attacker;
                        defeat_attacker(encounterMap, attacker, opponents, current);
                        break;
                    }
                    if (opponents.empty()) {
                        result.outcome = CFightOutcome::AttackerVictory;
                        result.survivor = attacker;
                        result.opponent = current;
                        break;
                    }
                    current = resolve_target(encounterMap, attacker, opponents, current);
                } else {
                    update_combat_status(encounterMap, attacker, opponents, combat_name(attacker) + " is stunned.");
                }
                continue;
            }

            auto opponentIt = std::find(opponents.begin(), opponents.end(), actor);
            if (opponentIt == opponents.end() || !is_active_participant(encounterMap, actor)) {
                continue;
            }

            update_combat_status(encounterMap, attacker, opponents,
                                 combat_name(actor) + " acts against " + combat_name(attacker) + ".");
            auto effect_result = apply_effects_with_result(actor);
            if (!actor->isAlive()) {
                if (remove_dead_opponents(encounterMap, attacker, opponents, effect_result.caster)) {
                    if (opponents.empty()) {
                        result.outcome = CFightOutcome::AttackerVictory;
                        result.survivor = attacker;
                        result.opponent = actor;
                        break;
                    }
                    current = resolve_target(encounterMap, attacker, opponents, current);
                }
                continue;
            }
            if (!CTags::isTagPresent(actor->getEffects(), CTag::Stun)) {
                if (auto controller = actor->getFightController()) {
                    controller->control(actor, attacker);
                    if (controller->isCancelled(actor, attacker)) {
                        result.outcome = CFightOutcome::Cancelled;
                        result.survivor = attacker;
                        result.opponent = actor;
                        break;
                    }
                }
                if (!attacker->isAlive()) {
                    remove_dead_opponents(encounterMap, attacker, opponents, attacker);
                    result.outcome = CFightOutcome::AttackerDefeat;
                    result.survivor = actor;
                    result.opponent = attacker;
                    defeat_attacker(encounterMap, attacker, opponents, actor);
                    break;
                }
            } else {
                update_combat_status(encounterMap, attacker, opponents, combat_name(actor) + " is stunned.");
            }
            if (remove_dead_opponents(encounterMap, attacker, opponents, attacker)) {
                if (opponents.empty()) {
                    result.outcome = CFightOutcome::AttackerVictory;
                    result.survivor = attacker;
                    result.opponent = actor;
                    break;
                }
                current = resolve_target(encounterMap, attacker, opponents, current);
            }
        }

        if (result.outcome != CFightOutcome::Invalid || !is_active_participant(encounterMap, attacker)) {
            break;
        }
        if (opponents.empty()) {
            result.outcome = CFightOutcome::AttackerVictory;
            result.survivor = attacker;
            result.opponent = current;
            break;
        }

        auto after = encounter_state(attacker, opponents);
        stale_turns = after == before ? stale_turns + 1 : 0;
    }

    if (result.outcome == CFightOutcome::Invalid) {
        if (!is_active_participant(encounterMap, attacker)) {
            result.outcome = CFightOutcome::AttackerDefeat;
            result.opponent = attacker;
        } else if (opponents.empty()) {
            result.outcome = CFightOutcome::AttackerVictory;
            result.survivor = attacker;
            result.opponent = current;
        } else {
            result.outcome = CFightOutcome::Stalled;
            result.survivor = attacker;
            result.opponent = current;
        }
    }

    controllerEndGuard.endAll();

    if (result.outcome != CFightOutcome::Invalid) {
        const bool include_initiative = result.outcome != CFightOutcome::AttackerDefeat;
        update_combat_status(encounterMap, attacker, opponents,
                             final_status_message(result.outcome, attackerName, result.rounds), include_initiative);
    }

    if (CPlaytestTrace::enabled()) {
        json fields = {
            {"attacker", CPlaytestTrace::objectRef(attacker)},
            {"opponents", CPlaytestTrace::objectRefs(allOpponents)},
            {"outcome", static_cast<int>(result.outcome)},
            {"outcomeName", final_status_message(result.outcome, attackerName, result.rounds)},
            {"rounds", result.rounds},
            {"survivor", CPlaytestTrace::objectRef(result.survivor)},
        };
        CPlaytestTrace::addMapContext(fields, encounterMap);
        CPlaytestTrace::record("combat_finished", fields);
    }

    return result;
}

} // namespace

bool CFightResult::resolved() const {
    return outcome == CFightOutcome::AttackerVictory || outcome == CFightOutcome::AttackerDefeat;
}

bool CFightResult::attackerSucceeded() const { return outcome == CFightOutcome::AttackerVictory; }

bool CFightHandler::fight(std::shared_ptr<CCreature> a, std::shared_ptr<CCreature> b) { return fightMany(a, {b}); }

bool CFightHandler::fightMany(std::shared_ptr<CCreature> attacker,
                              const std::vector<std::shared_ptr<CCreature>> &encounterOpponents) {
    return fightManyResult(attacker, encounterOpponents).resolved();
}

CFightOutcome CFightHandler::fightManyOutcome(std::shared_ptr<CCreature> attacker,
                                              const std::vector<std::shared_ptr<CCreature>> &encounterOpponents) {
    return fightManyResult(attacker, encounterOpponents).outcome;
}

CFightResult CFightHandler::fightManyResult(std::shared_ptr<CCreature> attacker,
                                            const std::vector<std::shared_ptr<CCreature>> &encounterOpponents) {
    return resolve_fight_many(attacker, encounterOpponents);
}

void CFightHandler::defeatedCreature(const std::shared_ptr<CCreature> &a, const std::shared_ptr<CCreature> &b) {
    auto encounterMap = b ? b->getMap() : nullptr;
    if (!a || !b || !a->isAlive() || b->isAlive() || !is_registered_on_map(encounterMap, a) ||
        !is_registered_on_map(encounterMap, b) || a == b) {
        return;
    }
    vstd::logger::debug(a->to_string(), a->getName(), "defeated", b->to_string());
    a->addExpScaled(b->getScale());
    // TODO: loot handler
    std::set<std::shared_ptr<CItem>> items = b->getGame()->getRngHandler()->getRandomLoot(b->getScale());
    for (const std::shared_ptr<CItem> &item : b->getInInventory()) {
        if (!b->isPlayer() || !item->hasTag(CTag::Quest)) {
            b->removeItem(item);
            items.insert(item);
        }
    }
    if (CPlaytestTrace::enabled()) {
        json fields = {
            {"defeated", CPlaytestTrace::objectRef(b)},
            {"items", CPlaytestTrace::itemRefs(items)},
            {"recipient", CPlaytestTrace::objectRef(a)},
            {"rewardSource", "combat"},
            {"scale", b->getScale()},
        };
        CPlaytestTrace::addMapContext(fields, encounterMap);
        CPlaytestTrace::record("reward_granted", fields);
    }
    a->getGame()->getRngHandler()->addRandomLoot(a, items);
    encounterMap->removeObject(b);
}

void CFightHandler::applyEffects(const std::shared_ptr<CCreature> &cr) { apply_effects_with_result(cr); }
