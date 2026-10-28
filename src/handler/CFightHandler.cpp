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
#include <limits>
#include "core/CAsync.h"
#include <algorithm>
#include <exception>
#include <functional>
#include <sstream>
#include <tuple>
#include <unordered_set>
#include <utility>

#include "core/CController.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CMap.h"
#include "core/CPlaytestTrace.h"
#include "core/CTags.h"
#include "object/CCreature.h"
#include "object/CEffect.h"
#include "object/CPlayer.h"
#include "gui/CGui.h"
#include "handler/CGuiHandler.h"
#include "handler/CRngHandler.h"
#include "handler/CSevenSunsMerchantDialogue.h"

struct CCombatOwnership {
    CCombatOwnership() = default;
    CCombatOwnership(const CCombatOwnership &) = delete;
    CCombatOwnership &operator=(const CCombatOwnership &) = delete;
    CCombatOwnership(CCombatOwnership &&) = delete;
    CCombatOwnership &operator=(CCombatOwnership &&) = delete;
    std::optional<CGameContext::UnsafeOperationLease> defeatAdmission;
    std::function<void()> defeatPresentation;
};

class CCombatParticipantGuard {
  public:
    static bool isOwned(const std::shared_ptr<CCreature> &participant) {
        return participant && (!participant->activeCombatOwner.expired() || participant->defeatResolutionInProgress ||
                               participant->defeatResolutionUncertain || participant->activeDefeatRecipientCount != 0);
    }

    static vstd::task<void> resolveDefeat(std::shared_ptr<CCreature> winner, std::shared_ptr<CCreature> loser,
                                          std::shared_ptr<CCombatOwnership> identity) {
        return CFightHandler::resolveOwnedDefeatAsync(std::move(winner), std::move(loser), std::move(identity));
    }

    CCombatParticipantGuard(std::shared_ptr<CMap> map, std::vector<std::shared_ptr<CCreature>> participants)
        : map(std::move(map)), participants(std::move(participants)), identity(std::make_shared<CCombatOwnership>()) {
        if (this->map && this->map->activeCombatTransitionDeferrals == std::numeric_limits<std::size_t>::max()) {
            return;
        }
        for (const auto &participant : this->participants) {
            if (!participant || isOwned(participant)) {
                return;
            }
        }
        for (const auto &participant : this->participants) {
            participant->activeCombatOwner = identity;
        }
        if (this->map) {
            ++this->map->activeCombatTransitionDeferrals;
        }
        admitted = true;
    }

    CCombatParticipantGuard(const CCombatParticipantGuard &) = delete;
    CCombatParticipantGuard &operator=(const CCombatParticipantGuard &) = delete;
    CCombatParticipantGuard(CCombatParticipantGuard &&) = delete;
    CCombatParticipantGuard &operator=(CCombatParticipantGuard &&) = delete;

    ~CCombatParticipantGuard() {
        if (admitted) {
            for (const auto &participant : participants) {
                if (participant->activeCombatOwner.lock() == identity) {
                    participant->activeCombatOwner.reset();
                }
            }
            if (map) {
                --map->activeCombatTransitionDeferrals;
            }
        }
    }

    explicit operator bool() const { return admitted; }
    std::shared_ptr<CCombatOwnership> getIdentity() const { return admitted ? identity : nullptr; }

    void settleDefeatAdmission() {
        if (!admitted) {
            return;
        }
        if (identity->defeatAdmission && !identity->defeatAdmission->isCurrent()) {
            identity->defeatPresentation = {};
            identity->defeatAdmission->quarantine();
            return;
        }
        auto present = std::exchange(identity->defeatPresentation, {});
        if (present) {
            present();
        }
        if (identity->defeatAdmission) {
            identity->defeatAdmission->finish();
        }
    }

  private:
    std::shared_ptr<CMap> map;
    std::vector<std::shared_ptr<CCreature>> participants;
    std::shared_ptr<CCombatOwnership> identity;
    bool admitted = false;
};

bool CFightHandler::hasActiveCombatClaim(const std::shared_ptr<CCreature> &actor) {
    return CCombatParticipantGuard::isOwned(actor);
}

template <typename Callback> class DefeatScopeExit {
  public:
    explicit DefeatScopeExit(Callback callback) : callback(std::move(callback)) {}
    DefeatScopeExit(const DefeatScopeExit &) = delete;
    DefeatScopeExit &operator=(const DefeatScopeExit &) = delete;
    DefeatScopeExit(DefeatScopeExit &&) = delete;
    DefeatScopeExit &operator=(DefeatScopeExit &&) = delete;
    ~DefeatScopeExit() noexcept { callback(); }

  private:
    Callback callback;
};

namespace {
vstd::task<void> showDefeatOwnedAsync(std::weak_ptr<CGame> weakGame, std::weak_ptr<CMap> weakMap,
                                      std::weak_ptr<CCreature> weakPlayer,
                                      CGameContext::TransitionGeneration generation) {
    try {
        co_await vstd::post(vstd::event_loop<>::instance());
        auto game = weakGame.lock();
        auto map = weakMap.lock();
        auto player = weakPlayer.lock();
        if (!game || !map || !player || game->getMap() != map || map->getPlayer() != player || !game->getGui() ||
            !game->getContext()->isTransitionGenerationCurrent(generation)) {
            co_return;
        }
        auto gui = game->getGuiHandler();
        game.reset();
        map.reset();
        player.reset();
        co_await gui->showDefeatAsync();
    } catch (const vstd::task_cancelled &) {
        throw;
    } catch (const vstd::scheduler_rejected &) {
        throw;
    } catch (const std::exception &error) {
        vstd::logger::error("Defeat recovery presentation failed: " + std::string(error.what()));
    }
}

using encounter_type = std::vector<std::shared_ptr<CCreature>>;
using effect_state_type = std::tuple<std::string, std::string, int>;
using creature_state_type = std::tuple<std::string, int, int, std::vector<effect_state_type>, std::size_t>;

struct effect_application_result {
    bool died = false;
    std::shared_ptr<CCreature> caster;
};

class FightControllerEndGuard {
  public:
    ~FightControllerEndGuard() noexcept {
        try {
            endAll();
        } catch (...) {
        }
    }

    void start(const std::shared_ptr<CFightController> &controller, const std::shared_ptr<CCreature> &creature,
               const std::shared_ptr<CCreature> &opponent) {
        if (!controller) {
            return;
        }
        startedControllers.push_back({controller, creature, opponent, nullptr, false});
        controller->start(creature, opponent);
    }

    void start(const std::shared_ptr<CFightController> &controller, const std::shared_ptr<CCreature> &creature,
               const std::shared_ptr<CCreature> *opponent) {
        if (!controller) {
            return;
        }
        startedControllers.push_back({controller, creature, std::shared_ptr<CCreature>(), opponent, false});
        controller->start(creature, opponent ? *opponent : std::shared_ptr<CCreature>());
    }

    void endAll() {
        std::exception_ptr failure;
        for (auto &started : startedControllers) {
            if (started.ended || !started.controller) {
                continue;
            }
            started.ended = true;
            try {
                started.controller->end(started.creature,
                                        started.currentOpponent ? *started.currentOpponent : started.startedOpponent);
            } catch (...) {
                if (!failure) {
                    failure = std::current_exception();
                }
            }
        }
        if (failure) {
            std::rethrow_exception(failure);
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

auto encounter_state(const std::shared_ptr<CCreature> &attacker, const encounter_type &opponents,
                     const encounter_type &allies = {}) {
    std::vector<creature_state_type> state;
    state.push_back(creature_state(attacker));
    for (const auto &opponent : opponents) {
        state.push_back(creature_state(opponent));
    }
    for (const auto &ally : allies) {
        state.push_back(creature_state(ally));
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
                                const encounter_type &opponents, const encounter_type &allies = {}) {
    encounter_type order;
    if (is_active_participant(encounterMap, attacker)) {
        order.push_back(attacker);
    }
    for (const auto &opponent : opponents) {
        if (is_active_participant(encounterMap, opponent)) {
            order.push_back(opponent);
        }
    }
    for (const auto &ally : allies) {
        if (is_active_participant(encounterMap, ally)) {
            order.push_back(ally);
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
                          const encounter_type &opponents, const std::string &message, bool includeInitiative = true,
                          const encounter_type &allies = {}) {
    if (!encounterMap) {
        return;
    }
    auto status = message;
    if (includeInitiative) {
        const auto turnOrder = build_turn_order(encounterMap, attacker, opponents, allies);
        if (!status.empty()) {
            status += "\n";
        }
        status += format_turn_order(turnOrder);
    }
    CFightHandler::recordCombatStatus(encounterMap, status);
}

void clear_combat_status(const std::shared_ptr<CMap> &encounterMap) { CFightHandler::resetCombatHistory(encounterMap); }

void cancel_fight(CFightResult &result, const std::shared_ptr<CCreature> &survivor,
                  const std::shared_ptr<CCreature> &opponent) {
    result.outcome = CFightOutcome::Cancelled;
    result.survivor = survivor;
    result.opponent = opponent;
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

encounter_type sanitize_allies(const std::shared_ptr<CMap> &map, const std::shared_ptr<CCreature> &hero,
                               const encounter_type &candidates, const encounter_type &opponents) {
    encounter_type allies;
    if (!hero || !hero->isPlayer() || !map || map->getPlayer() != hero || !is_active_participant(map, hero)) {
        return allies;
    }
    std::unordered_set<const CCreature *> identities;
    for (const auto &ally : candidates) {
        if (!is_active_participant(map, ally) || ally->isPlayer() || ally == hero ||
            ally->getPosZ() != hero->getPosZ() || !hero->isAffiliatedWith(ally) ||
            contains_participant(opponents, ally) || !ally->getFightController() ||
            dynamic_cast<CPlayerFightController *>(ally->getFightController().get()) ||
            !identities.insert(ally.get()).second) {
            continue;
        }
        allies.push_back(ally);
        if (allies.size() == CFightHandler::MaximumAllies) {
            break;
        }
    }
    std::sort(allies.begin(), allies.end(), [](const auto &left, const auto &right) {
        return left->getName() < right->getName();
    });
    return allies;
}

encounter_type configured_allies(const std::shared_ptr<CMap> &map, const std::shared_ptr<CCreature> &hero) {
    if (!map || !hero || !map->getBoolProperty("plugin_cityAlliedCombat")) {
        return {};
    }
    auto radius = map->getNumericProperty("plugin_cityCompanionCombatRadius");
    radius = radius > 0 ? std::clamp(radius, 1, 16) : 8;
    std::istringstream names(map->getStringProperty("plugin_cityCompanionNames").substr(0, 2048));
    encounter_type candidates;
    std::string name;
    for (int examined = 0; examined < 32 && std::getline(names, name, ','); ++examined) {
        auto ally = std::dynamic_pointer_cast<CCreature>(map->getObjectByName(name));
        if (ally && ally->getPosZ() == hero->getPosZ() &&
            map->getDistance(hero->getCoords(), ally->getCoords()) <= radius) {
            candidates.push_back(ally);
        }
    }
    return sanitize_allies(map, hero, candidates, {});
}

encounter_type living_side(const std::shared_ptr<CMap> &map, const std::shared_ptr<CCreature> &hero,
                            const encounter_type &allies) {
    encounter_type side;
    if (is_active_participant(map, hero)) {
        side.push_back(hero);
    }
    for (const auto &ally : allies) {
        if (is_active_participant(map, ally) && hero->isAffiliatedWith(ally) && ally->getPosZ() == hero->getPosZ()) {
            side.push_back(ally);
        }
    }
    return side;
}

std::shared_ptr<CCreature> nearest_target(const std::shared_ptr<CMap> &map,
                                         const std::shared_ptr<CCreature> &actor, const encounter_type &side) {
    if (side.empty()) {
        return nullptr;
    }
    return *std::min_element(side.begin(), side.end(), [&](const auto &left, const auto &right) {
        return map->getDistance(actor->getCoords(), left->getCoords()) <
               map->getDistance(actor->getCoords(), right->getCoords());
    });
}

vstd::task<void> remove_dead_allies_async(std::shared_ptr<CMap> map, const std::shared_ptr<CCreature> &hero,
                                          encounter_type &allies, const encounter_type &opponents,
                                          std::shared_ptr<CCreature> winner,
                                          std::shared_ptr<CCombatOwnership> encounterOwner) {
    for (auto it = allies.begin(); it != allies.end();) {
        const auto ally = *it;
        if (is_active_participant(map, ally) && hero->isAffiliatedWith(ally) && ally->getPosZ() == hero->getPosZ()) {
            ++it;
            continue;
        }
        if (ally && !ally->isAlive() && is_registered_on_map(map, ally)) {
            if (is_active_participant(map, winner) && contains_participant(opponents, winner) && winner != hero) {
                co_await CCombatParticipantGuard::resolveDefeat(winner, ally, encounterOwner);
            } else {
                co_await map->removeObjectAsync(ally);
            }
        }
        it = allies.erase(it);
    }
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

vstd::task<bool> resolve_defeat_async(std::shared_ptr<CMap> encounterMap, std::shared_ptr<CCreature> attacker,
                                      const encounter_type &opponents, std::shared_ptr<CCreature> loser,
                                      std::shared_ptr<CCreature> winner,
                                      std::shared_ptr<CCombatOwnership> encounterOwner) {
    if (!loser || loser->isAlive() || !is_registered_on_map(encounterMap, loser)) {
        co_return false;
    }
    if (is_reward_eligible_winner(encounterMap, attacker, opponents, loser, winner)) {
        co_await CCombatParticipantGuard::resolveDefeat(winner, loser, encounterOwner);
    } else {
        co_await encounterMap->removeObjectAsync(loser);
    }
    co_return true;
}

vstd::task<bool> remove_dead_opponents_async(std::shared_ptr<CMap> encounterMap, std::shared_ptr<CCreature> attacker,
                                             encounter_type &opponents, std::shared_ptr<CCreature> winner,
                                             std::shared_ptr<CCombatOwnership> encounterOwner) {
    bool changed = false;
    for (auto it = opponents.begin(); it != opponents.end();) {
        auto opponent = *it;
        if (opponent && is_registered_on_map(encounterMap, opponent) && opponent->isAlive()) {
            ++it;
            continue;
        }
        changed = true;
        if (opponent && is_registered_on_map(encounterMap, opponent)) {
            co_await resolve_defeat_async(encounterMap, attacker, opponents, opponent, winner, encounterOwner);
        }
        it = opponents.erase(it);
    }
    co_return changed;
}

vstd::task<void> defeat_attacker_async(std::shared_ptr<CMap> encounterMap, std::shared_ptr<CCreature> attacker,
                                       const encounter_type &opponents, std::shared_ptr<CCreature> winner,
                                       std::shared_ptr<CCombatOwnership> encounterOwner) {
    co_await resolve_defeat_async(encounterMap, attacker, opponents, attacker, winner, encounterOwner);
}

effect_application_result apply_effects_with_result(const std::shared_ptr<CCreature> &cr,
                                                    const std::function<bool()> &canApply = {}) {
    effect_application_result result;
    if (!cr) {
        vstd::logger::warning("Skipping effect application for null creature");
        return result;
    }

    auto effects = cr->getEffects();
    for (const auto &effect : effects) {
        if (canApply && !canApply()) {
            return result;
        }
        if (!effect) {
            vstd::logger::warning("Skipping null effect while expiring effects for", cr->to_string());
            continue;
        }
        if (effect->getTimeLeft() == 0) {
            vstd::logger::debug(cr->to_string(), "is now free from", effect->to_string());
            if (canApply && !canApply()) {
                return result;
            }
            cr->removeEffect(effect);
        }
    }

    effects = cr->getEffects();
    const bool buffsFirst = effects.size() > 1 && cr->getHp() < cr->getHpMax();
    using tick_key_type = std::tuple<bool, std::string, std::string, std::string>;
    std::vector<std::pair<tick_key_type, std::shared_ptr<CEffect>>> orderedEffects;
    orderedEffects.reserve(effects.size());
    for (const auto &effect : effects) {
        if (!effect) {
            vstd::logger::warning("Skipping null effect while applying effects for", cr->to_string());
            continue;
        }
        // Recover first while hurt; at full health, let other ticks create room for recovery.
        auto key = effects.size() > 1 ? tick_key_type{effect->hasTag(CTag::Buff) != buffsFirst, effect->getTypeId(),
                                                      effect->getType(), effect->getName()}
                                      : tick_key_type{};
        orderedEffects.emplace_back(std::move(key), effect);
    }
    std::sort(orderedEffects.begin(), orderedEffects.end(),
              [](const auto &left, const auto &right) { return left.first < right.first; });
    for (const auto &entry : orderedEffects) {
        if (canApply && !canApply()) {
            return result;
        }
        const auto &effect = entry.second;
        const bool was_alive = cr->isAlive();
        vstd::logger::debug(cr->to_string(), "suffers from", effect->to_string());
        if (canApply && !canApply()) {
            break;
        }
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

vstd::task<CFightResult> resolveConfiguredFightAsync(std::shared_ptr<CCreature> attacker, encounter_type opponents);

vstd::task<CFightResult> resolveFightManyAsync(std::shared_ptr<CCreature> attacker, encounter_type encounterOpponents,
                                             encounter_type encounterAllies = {}, bool useConfiguredAllies = true) {
    auto loop = vstd::event_loop<>::instance();
    if (!loop->isMainThread()) {
        co_await vstd::post(loop);
    }
    CFightResult result;
    if (!attacker) {
        co_return result;
    }
    if (CCombatParticipantGuard::isOwned(attacker)) {
        result.outcome = CFightOutcome::Cancelled;
        co_return result;
    }
    auto encounterMap = attacker->getMap();
    std::optional<CGameContext::UnsafeOperationLease> nativeAdmission;
    if (encounterMap && encounterMap->getBoolProperty("guardNativeEncounterSaves")) {
        nativeAdmission = encounterMap->tryBeginUnsafeOperation();
        if (!nativeAdmission) {
            co_return result;
        }
    }
    CCombatParticipantGuard *ownedParticipants = nullptr;
    FightControllerEndGuard *ownedControllers = nullptr;
    bool controllersSettled = false;
    const auto certifyCleanup = [&] {
        if (ownedControllers && !controllersSettled) {
            ownedControllers->endAll();
            controllersSettled = true;
        }
    };
    const auto settle_result = [&](CFightResult value) {
        certifyCleanup();
        if (ownedParticipants) {
            ownedParticipants->settleDefeatAdmission();
        }
        if (nativeAdmission) {
            if (nativeAdmission->isCurrent()) {
                nativeAdmission->finish();
            } else {
                nativeAdmission->quarantine();
            }
        }
        return value;
    };

    if (useConfiguredAllies && encounterMap && encounterMap->getBoolProperty("plugin_cityAlliedCombat")) {
        result = co_await resolveConfiguredFightAsync(std::move(attacker), std::move(encounterOpponents));
        co_return settle_result(result);
    }
    const auto attackerName = combat_name(attacker);
    auto opponents = sanitize_opponents(encounterMap, attacker, encounterOpponents);

    auto allies = sanitize_allies(encounterMap, attacker, encounterAllies, opponents);
    const auto allAllies = allies;
    auto participants = opponents;
    participants.push_back(attacker);
    participants.insert(participants.end(), allies.begin(), allies.end());
    CCombatParticipantGuard participantGuard(encounterMap, std::move(participants));
    if (!participantGuard) {
        result.outcome = CFightOutcome::Cancelled;
        co_return settle_result(result);
    }
    ownedParticipants = &participantGuard;
    const auto encounterOwner = participantGuard.getIdentity();
    if (!is_active_participant(encounterMap, attacker) || opponents.empty()) {
        clear_combat_status(encounterMap);
        co_return settle_result(result);
    }
    CFightHandler::resetCombatHistory(encounterMap);
    const bool alliedEncounter = !allies.empty();
    std::weak_ptr<CGame> encounterGame = attacker->getGame();
    auto game = encounterGame.lock();
    std::weak_ptr<CGameContext> encounterContext = game ? game->getContext() : nullptr;
    const auto generation = game ? game->getContext()->captureTransitionGeneration() : 0;
    game.reset();
    const auto contextIsCurrent = [&] {
        if (nativeAdmission && !nativeAdmission->isCurrent()) {
            return false;
        }
        if (!alliedEncounter) {
            return true;
        }
        auto owner = encounterGame.lock();
        auto context = encounterContext.lock();
        return owner && context && context->isTransitionGenerationCurrent(generation) && owner->getMap() == encounterMap;
    };
    std::function<bool()> effectContext;
    if (nativeAdmission) {
        effectContext = contextIsCurrent;
    }
    const auto status = [&](const std::string &message, bool initiative = true) {
        update_combat_status(encounterMap, attacker, opponents, message, initiative, allies);
    };

    auto allOpponents = opponents;
    auto current = opponents.front();
    auto attackerController = attacker->getFightController();
    if (!attackerController) {
        clear_combat_status(encounterMap);
        co_return settle_result(result);
    }
    attackerController->setOpponents(attacker, opponents);
    if (nativeAdmission && !nativeAdmission->isCurrent()) {
        cancel_fight(result, attacker, current);
        co_return settle_result(result);
    }
    FightControllerEndGuard controllerEndGuard;
    ownedControllers = &controllerEndGuard;
    controllerEndGuard.start(attackerController, attacker, &current);
    for (const auto &opponent : allOpponents) {
        if ((alliedEncounter || nativeAdmission.has_value()) &&
            (!contextIsCurrent() || !is_active_participant(encounterMap, opponent))) {
            continue;
        }
        if (auto controller = opponent->getFightController()) {
            controllerEndGuard.start(controller, opponent, attacker);
        }
    }
    for (const auto &ally : allAllies) {
        if (!contextIsCurrent() || !is_active_participant(encounterMap, ally)) {
            continue;
        }
        if (auto controller = ally->getFightController()) {
            controller->setOpponents(ally, opponents);
            if (nativeAdmission && !contextIsCurrent()) {
                cancel_fight(result, attacker, current);
                co_return settle_result(result);
            }
            controllerEndGuard.start(controller, ally, current);
        }
    }
    if (CPlaytestTrace::enabled()) {
        json fields = {
            {"attacker", CPlaytestTrace::objectRef(attacker)},
            {"opponents", CPlaytestTrace::objectRefs(allOpponents)},
        };
        const auto snapshot = [](const std::shared_ptr<CCreature> &creature, const json &object) {
            return json{
                {"object", object},
                {"coords", CPlaytestTrace::coords(creature->getCoords())},
                {"hp", creature->getHp()},
                {"hpMax", creature->getHpMax()},
                {"mana", creature->getMana()},
                {"manaMax", creature->getManaMax()},
                {"level", creature->getLevel()},
            };
        };
        fields["attackerState"] = snapshot(attacker, fields["attacker"]);
        fields["opponentStates"] = json::array();
        for (std::size_t index = 0; index < allOpponents.size(); ++index) {
            fields["opponentStates"][index] = snapshot(allOpponents[index], fields["opponents"][index]);
        }
        if (alliedEncounter) {
            fields["allies"] = CPlaytestTrace::objectRefs(allAllies);
            fields["allyStates"] = json::array();
            for (std::size_t index = 0; index < allAllies.size(); ++index) {
                fields["allyStates"][index] = snapshot(allAllies[index], fields["allies"][index]);
            }
        }
        CPlaytestTrace::addMapContext(fields, encounterMap);
        CPlaytestTrace::record("combat_started", fields);
    }

    auto finish_result = [&]() -> CFightResult {
        certifyCleanup();

        if (result.outcome != CFightOutcome::Invalid) {
            const bool include_initiative = result.outcome != CFightOutcome::AttackerDefeat;
            status(final_status_message(result.outcome, attackerName, result.rounds), include_initiative);
        }

        if (CPlaytestTrace::enabled()) {
            json fields = {
                {"attacker", CPlaytestTrace::objectRef(attacker)},
                {"opponents", CPlaytestTrace::objectRefs(allOpponents)},
                {"outcome", std::to_underlying(result.outcome)},
                {"outcomeName", final_status_message(result.outcome, attackerName, result.rounds)},
                {"rounds", result.rounds},
                {"survivor", CPlaytestTrace::objectRef(result.survivor)},
            };
            if (alliedEncounter) {
                fields["allies"] = CPlaytestTrace::objectRefs(allAllies);
            }
            CPlaytestTrace::addMapContext(fields, encounterMap);
            CPlaytestTrace::record("combat_finished", fields);
        }

        return settle_result(result);
    };

    int stale_turns = 0;
    for (int turn = 0; turn < 100 && stale_turns < 20 && result.outcome == CFightOutcome::Invalid &&
                       is_active_participant(encounterMap, attacker) && !opponents.empty();
         ++turn) {
        if (!contextIsCurrent() || loop->quitRequested() || SDL_HasEvent(SDL_QUIT)) {
            cancel_fight(result, attacker, current);
            break;
        }
        result.rounds = turn + 1;
        encounterMap->setNumericProperty("combatRound", result.rounds);
        status("Combat round " + vstd::str(turn + 1) + " begins.");
        auto before = encounter_state(attacker, opponents, allies);
        const auto turnOrder = build_turn_order(encounterMap, attacker, opponents, allies);

        for (const auto &actor : turnOrder) {
            if (result.outcome != CFightOutcome::Invalid || !is_active_participant(encounterMap, attacker) ||
                opponents.empty()) {
                break;
            }
            if (!contextIsCurrent()) {
                cancel_fight(result, attacker, current);
                co_return finish_result();
            }

            if (actor == attacker) {
                current = resolve_target(encounterMap, attacker, opponents, current);
                if (alliedEncounter && (!contextIsCurrent() || !is_active_participant(encounterMap, current))) {
                    cancel_fight(result, attacker, current);
                    co_return finish_result();
                }
                status(combat_name(attacker) + " acts against " + combat_name(current) + ".");

                if (nativeAdmission && !contextIsCurrent()) {
                    cancel_fight(result, attacker, current);
                    co_return finish_result();
                }
                auto effect_result = apply_effects_with_result(attacker, effectContext);
                if (nativeAdmission && !contextIsCurrent()) {
                    cancel_fight(result, attacker, current);
                    co_return finish_result();
                }
                if (!attacker->isAlive()) {
                    result.outcome = CFightOutcome::AttackerDefeat;
                    result.survivor = effect_result.caster;
                    result.opponent = attacker;
                    co_await defeat_attacker_async(encounterMap, attacker, opponents, effect_result.caster,
                                                   encounterOwner);
                    break;
                }

                if (!CTags::isTagPresent(attacker->getEffects(), CTag::Stun)) {
                    if (nativeAdmission && !contextIsCurrent()) {
                        cancel_fight(result, attacker, current);
                        co_return finish_result();
                    }
                    co_await attackerController->controlAsync(attacker, current);
                    if (!contextIsCurrent() || attackerController->isCancelled(attacker, current)) {
                        cancel_fight(result, attacker, current);
                        co_return finish_result();
                    }
                    if (alliedEncounter) {
                        co_await remove_dead_allies_async(encounterMap, attacker, allies, opponents, nullptr,
                                                          encounterOwner);
                    }
                    if (!contextIsCurrent()) {
                        cancel_fight(result, attacker, current);
                        co_return finish_result();
                    }
                    co_await remove_dead_opponents_async(encounterMap, attacker, opponents, attacker, encounterOwner);
                    if (!contextIsCurrent()) {
                        cancel_fight(result, attacker, current);
                        co_return finish_result();
                    }
                    if (!attacker->isAlive()) {
                        result.outcome = CFightOutcome::AttackerDefeat;
                        result.survivor = current;
                        result.opponent = attacker;
                        co_await defeat_attacker_async(encounterMap, attacker, opponents, current, encounterOwner);
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
                    status(combat_name(attacker) + " is stunned.");
                }
                continue;
            }

            if (contains_participant(allies, actor)) {
                if (!is_active_participant(encounterMap, actor) || !attacker->isAffiliatedWith(actor) ||
                    actor->getPosZ() != attacker->getPosZ()) {
                    std::erase(allies, actor);
                    continue;
                }
                if (nativeAdmission && !contextIsCurrent()) {
                    cancel_fight(result, attacker, current);
                    co_return finish_result();
                }
                const auto effects = apply_effects_with_result(actor, effectContext);
                if (nativeAdmission && !contextIsCurrent()) {
                    cancel_fight(result, attacker, current);
                    co_return finish_result();
                }
                if (!actor->isAlive()) {
                    co_await remove_dead_allies_async(encounterMap, attacker, allies, opponents, effects.caster,
                                                      encounterOwner);
                    continue;
                }
                if (CTags::isTagPresent(actor->getEffects(), CTag::Stun)) {
                    status(combat_name(actor) + " is stunned.");
                    continue;
                }
                auto target = resolve_target(encounterMap, actor, opponents, nearest_target(encounterMap, actor, opponents));
                auto controller = actor->getFightController();
                if (!contextIsCurrent()) {
                    cancel_fight(result, attacker, target);
                    co_return finish_result();
                }
                if (!controller || dynamic_cast<CPlayerFightController *>(controller.get()) || !target) {
                    continue;
                }
                if (!is_active_participant(encounterMap, actor) || !is_active_participant(encounterMap, target)) {
                    continue;
                }
                status(combat_name(actor) + " assists against " + combat_name(target) + ".");
                if (nativeAdmission && !contextIsCurrent()) {
                    cancel_fight(result, attacker, target);
                    co_return finish_result();
                }
                co_await controller->controlAsync(actor, target);
                if (!contextIsCurrent() || controller->isCancelled(actor, target)) {
                    cancel_fight(result, attacker, target);
                    co_return finish_result();
                }
                if (CPlaytestTrace::enabled()) {
                    json fields = {{"actor", CPlaytestTrace::objectRef(actor)},
                                   {"target", CPlaytestTrace::objectRef(target)}, {"round", result.rounds}};
                    CPlaytestTrace::addMapContext(fields, encounterMap);
                    CPlaytestTrace::record("combat_ally_acted", fields);
                }
                co_await remove_dead_allies_async(encounterMap, attacker, allies, opponents, nullptr, encounterOwner);
                if (!contextIsCurrent()) {
                    cancel_fight(result, attacker, target);
                    co_return finish_result();
                }
                co_await remove_dead_opponents_async(encounterMap, attacker, opponents, attacker, encounterOwner);
                if (!contextIsCurrent()) {
                    cancel_fight(result, attacker, target);
                    co_return finish_result();
                }
                if (!attacker->isAlive()) {
                    result.outcome = CFightOutcome::AttackerDefeat;
                    result.survivor = target;
                    result.opponent = attacker;
                    co_await defeat_attacker_async(encounterMap, attacker, opponents, target, encounterOwner);
                    break;
                }
                if (opponents.empty()) {
                    result.outcome = CFightOutcome::AttackerVictory;
                    result.survivor = attacker;
                    result.opponent = target;
                    break;
                }
                current = resolve_target(encounterMap, attacker, opponents, current);
                continue;
            }

            auto opponentIt = std::find(opponents.begin(), opponents.end(), actor);
            if (opponentIt == opponents.end() || !is_active_participant(encounterMap, actor)) {
                continue;
            }

            auto target = attacker;
            if (alliedEncounter) {
                auto defenders = living_side(encounterMap, attacker, allies);
                target = resolve_target(encounterMap, actor, defenders, nearest_target(encounterMap, actor, defenders));
                if (!contextIsCurrent()) {
                    cancel_fight(result, attacker, target);
                    co_return finish_result();
                }
                if (!is_active_participant(encounterMap, actor) || !is_active_participant(encounterMap, target)) {
                    continue;
                }
            }
            status(combat_name(actor) + " acts against " + combat_name(target) + ".");
            if (nativeAdmission && !contextIsCurrent()) {
                cancel_fight(result, attacker, actor);
                co_return finish_result();
            }
            auto effect_result = apply_effects_with_result(actor, effectContext);
            if (nativeAdmission && !contextIsCurrent()) {
                cancel_fight(result, attacker, actor);
                co_return finish_result();
            }
            if (!actor->isAlive()) {
                auto recipient = alliedEncounter ? attacker : effect_result.caster;
                if (co_await remove_dead_opponents_async(encounterMap, attacker, opponents, recipient,
                                                         encounterOwner)) {
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
                    if (nativeAdmission && !contextIsCurrent()) {
                        cancel_fight(result, attacker, target);
                        co_return finish_result();
                    }
                    co_await controller->controlAsync(actor, target);
                    if (!contextIsCurrent() || controller->isCancelled(actor, target)) {
                        cancel_fight(result, attacker, actor);
                        co_return finish_result();
                    }
                }
                if (alliedEncounter) {
                    co_await remove_dead_allies_async(encounterMap, attacker, allies, opponents, actor, encounterOwner);
                }
                if (!contextIsCurrent()) {
                    cancel_fight(result, attacker, actor);
                    co_return finish_result();
                }
                if (!attacker->isAlive()) {
                    co_await remove_dead_opponents_async(encounterMap, attacker, opponents, attacker, encounterOwner);
                    result.outcome = CFightOutcome::AttackerDefeat;
                    result.survivor = actor;
                    result.opponent = attacker;
                    co_await defeat_attacker_async(encounterMap, attacker, opponents, actor, encounterOwner);
                    break;
                }
            } else {
                status(combat_name(actor) + " is stunned.");
            }
            if (co_await remove_dead_opponents_async(encounterMap, attacker, opponents, attacker, encounterOwner)) {
                if (opponents.empty()) {
                    result.outcome = CFightOutcome::AttackerVictory;
                    result.survivor = attacker;
                    result.opponent = actor;
                    break;
                }
                current = resolve_target(encounterMap, attacker, opponents, current);
            }
        }

        if (!contextIsCurrent()) {
            cancel_fight(result, attacker, current);
            break;
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

        auto after = encounter_state(attacker, opponents, allies);
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

    co_return finish_result();
}

vstd::task<CFightResult> resolveConfiguredFightAsync(std::shared_ptr<CCreature> attacker, encounter_type opponents) {
    auto loop = vstd::event_loop<>::instance();
    if (!loop->isMainThread()) {
        co_await vstd::post(loop);
    }
    auto map = attacker ? attacker->getMap() : nullptr;
    auto hero = map && map->getBoolProperty("plugin_cityAlliedCombat") ? map->getPlayer() : nullptr;
    auto allies = configured_allies(map, hero);
    if (allies.empty()) {
        co_return co_await resolveFightManyAsync(std::move(attacker), std::move(opponents), encounter_type{}, false);
    }
    if (attacker == hero) {
        co_return co_await resolveFightManyAsync(std::move(hero), std::move(opponents), std::move(allies), false);
    }
    const bool alliedMover = contains_participant(allies, attacker);
    const auto onHeroSide = [&](const auto &candidate) { return candidate == hero || contains_participant(allies, candidate); };
    if (alliedMover && std::none_of(opponents.begin(), opponents.end(), onHeroSide)) {
        auto result = co_await resolveFightManyAsync(hero, std::move(opponents), std::move(allies), false);
        if (result.outcome == CFightOutcome::AttackerVictory && is_active_participant(map, attacker)) {
            result.survivor = attacker;
        } else if (result.outcome == CFightOutcome::AttackerVictory) {
            result.outcome = CFightOutcome::AttackerDefeat;
            result.opponent = attacker;
        }
        co_return result;
    }
    if (attacker && !attacker->isAffiliatedWith(hero) && !opponents.empty() &&
        std::all_of(opponents.begin(), opponents.end(), onHeroSide)) {
        encounter_type enemies{attacker};
        auto result = co_await resolveFightManyAsync(hero, std::move(enemies), std::move(allies), false);
        if (result.outcome == CFightOutcome::AttackerVictory) {
            result.outcome = CFightOutcome::AttackerDefeat;
            result.opponent = attacker;
        } else if (result.outcome == CFightOutcome::AttackerDefeat) {
            result.outcome = CFightOutcome::AttackerVictory;
            result.opponent = hero;
        }
        co_return result;
    }
    co_return co_await resolveFightManyAsync(std::move(attacker), std::move(opponents), encounter_type{}, false);
}

} // namespace

std::vector<std::string> CFightHandler::getCombatHistory(const std::shared_ptr<CMap> &map) {
    if (!map)
        return {};
    std::vector<std::string> history;
    try {
        const auto stored = json::parse(map->getStringProperty("combatHistory"));
        if (stored.is_array()) {
            const auto first = stored.size() > CombatHistoryLimit ? stored.size() - CombatHistoryLimit : 0;
            for (auto index = first; index < stored.size(); ++index) {
                if (stored[index].is_string())
                    history.push_back(stored[index].get<std::string>());
            }
        }
    } catch (const std::exception &) {
        return {};
    }
    return history;
}

void CFightHandler::recordCombatStatus(const std::shared_ptr<CMap> &map, const std::string &status) {
    if (!map)
        return;
    map->setStringProperty("combatStatus", status);
    if (status.empty())
        return;
    auto history = getCombatHistory(map);
    history.push_back(status);
    if (history.size() > CombatHistoryLimit)
        history.erase(history.begin(), history.begin() + (history.size() - CombatHistoryLimit));
    auto stored = json::array();
    for (const auto &entry : history)
        stored[stored.size()] = entry;
    map->setStringProperty("combatHistory", stored.dump());
}

void CFightHandler::resetCombatHistory(const std::shared_ptr<CMap> &map) {
    if (!map)
        return;
    map->setStringProperty("combatStatus", "");
    map->setStringProperty("combatHistory", "");
    map->setNumericProperty("combatRound", 0);
}

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
    auto task = fightManyResultAsync(attacker, encounterOpponents);
    try {
        if (auto game = attacker ? attacker->getGame() : nullptr) {
            return game_async::wait(game->getContext()->spawnTask(std::move(task)),
                                    game->getGui() ? game_async::WaitMode::Frames : game_async::WaitMode::PostedWork);
        }
        return game_async::run(std::move(task), game_async::WaitMode::PostedWork);
    } catch (const vstd::task_cancelled &) {
        CFightResult result;
        cancel_fight(result, attacker, encounterOpponents.empty() ? nullptr : encounterOpponents.front());
        if (auto map = attacker ? attacker->getMap() : nullptr) {
            result.rounds = map->getNumericProperty("combatRound");
        }
        return result;
    }
}

vstd::task<CFightResult> CFightHandler::fightManyResultAsync(std::shared_ptr<CCreature> attacker,
                                                             std::vector<std::shared_ptr<CCreature>> opponents) {
    return resolveFightManyAsync(std::move(attacker), std::move(opponents));
}

bool CFightHandler::fightManyWithAllies(std::shared_ptr<CCreature> hero,
                                       const std::vector<std::shared_ptr<CCreature>> &opponents,
                                       const std::vector<std::shared_ptr<CCreature>> &allies) {
    return fightManyWithAlliesResult(std::move(hero), opponents, allies).resolved();
}

CFightOutcome CFightHandler::fightManyWithAlliesOutcome(std::shared_ptr<CCreature> hero,
                                                       const std::vector<std::shared_ptr<CCreature>> &opponents,
                                                       const std::vector<std::shared_ptr<CCreature>> &allies) {
    return fightManyWithAlliesResult(std::move(hero), opponents, allies).outcome;
}

CFightResult CFightHandler::fightManyWithAlliesResult(std::shared_ptr<CCreature> hero,
                                                     const std::vector<std::shared_ptr<CCreature>> &opponents,
                                                     const std::vector<std::shared_ptr<CCreature>> &allies) {
    auto task = fightManyWithAlliesResultAsync(hero, opponents, allies);
    try {
        if (auto game = hero ? hero->getGame() : nullptr) {
            return game_async::wait(game->getContext()->spawnTask(std::move(task)),
                                    game->getGui() ? game_async::WaitMode::Frames : game_async::WaitMode::PostedWork);
        }
        return game_async::run(std::move(task), game_async::WaitMode::PostedWork);
    } catch (const vstd::task_cancelled &) {
        CFightResult result;
        cancel_fight(result, hero, opponents.empty() ? nullptr : opponents.front());
        if (auto map = hero ? hero->getMap() : nullptr) {
            result.rounds = map->getNumericProperty("combatRound");
        }
        return result;
    }
}

vstd::task<CFightResult> CFightHandler::fightManyWithAlliesResultAsync(
    std::shared_ptr<CCreature> hero, std::vector<std::shared_ptr<CCreature>> opponents,
    std::vector<std::shared_ptr<CCreature>> allies) {
    return resolveFightManyAsync(std::move(hero), std::move(opponents), std::move(allies), false);
}

void CFightHandler::defeatedCreature(const std::shared_ptr<CCreature> &a, const std::shared_ptr<CCreature> &b) {
    auto task = defeatedCreatureAsync(a, b);
    if (auto game = b ? b->getGame() : nullptr) {
        game_async::wait(game->getContext()->spawnTask(std::move(task)),
                         game->getGui() ? game_async::WaitMode::Frames : game_async::WaitMode::PostedWork);
    } else {
        game_async::run(std::move(task), game_async::WaitMode::PostedWork);
    }
}

vstd::task<void> CFightHandler::defeatedCreatureAsync(std::shared_ptr<CCreature> a, std::shared_ptr<CCreature> b) {
    return resolveOwnedDefeatAsync(std::move(a), std::move(b), {});
}

vstd::task<void> CFightHandler::resolveOwnedDefeatAsync(std::shared_ptr<CCreature> a, std::shared_ptr<CCreature> b,
                                                        std::shared_ptr<CCombatOwnership> encounterOwner) {
    auto loop = vstd::event_loop<>::instance();
    if (!loop->isMainThread()) {
        co_await vstd::post(loop);
    }
    if (!a || !b || a == b) {
        co_return;
    }
    if (a->defeatResolutionInProgress || b->defeatResolutionInProgress || a->activeDefeatRecipientCount != 0 ||
        b->activeDefeatRecipientCount != 0) {
        throw std::logic_error("defeat recovery already owns a participant");
    }
    if (a->defeatResolutionUncertain || b->defeatResolutionUncertain) {
        throw std::logic_error("previous defeat recovery is uncertain");
    }
    auto winnerClaim = a->activeCombatOwner.lock();
    auto loserClaim = b->activeCombatOwner.lock();
    if ((winnerClaim || loserClaim || encounterOwner) &&
        (!encounterOwner || winnerClaim != encounterOwner || loserClaim != encounterOwner)) {
        throw std::logic_error("defeat finalization requires its private encounter owner");
    }
    auto encounterMap = b->getMap();
    const auto defeatedPlayer = std::dynamic_pointer_cast<CPlayer>(b);
    const auto capturedPlayer = encounterMap ? encounterMap->getAssignedPlayer() : nullptr;
    const bool playerDefeat = defeatedPlayer != nullptr;
    if (!a->isAlive() || b->isAlive() || !is_registered_on_map(encounterMap, a) ||
        !is_registered_on_map(encounterMap, b)) {
        co_return;
    }
    auto initialGame = b->getGame();
    auto initialContext = initialGame ? initialGame->getContext() : nullptr;
    const auto initialGeneration = initialContext ? initialContext->captureTransitionGeneration() : 0;
    const auto initialEpoch = initialGame ? initialGame->getMapBindingEpoch() : 0;
    std::weak_ptr<CGame> expectedGame = initialGame;
    initialGame.reset();
    const auto ownerIsCurrent = [expectedGame, initialContext, initialGeneration, initialEpoch, encounterMap, a, b,
                                 winnerClaim, loserClaim] {
        auto game = expectedGame.lock();
        return game && initialContext && initialContext->isActive() &&
               initialContext->isTransitionGenerationCurrent(initialGeneration) &&
               game->getMapBindingEpoch() == initialEpoch && encounterMap->getGame() == game &&
               b->defeatResolutionInProgress && a->activeDefeatRecipientCount != 0 &&
               game->getContext() == initialContext && game->getMap() == encounterMap && a->getGame() == game &&
               b->getGame() == game && a->getMap() == encounterMap && b->getMap() == encounterMap &&
               a->activeCombatOwner.lock() == winnerClaim && b->activeCombatOwner.lock() == loserClaim;
    };
    const auto requireOwnerCurrent = [ownerIsCurrent] {
        if (!ownerIsCurrent()) {
            throw vstd::task_cancelled();
        }
    };
    const auto requireDefeatCurrent = [ownerIsCurrent, encounterMap, a, b] {
        if (!ownerIsCurrent() || !a->isAlive() || b->isAlive() || !is_registered_on_map(encounterMap, a) ||
            !is_registered_on_map(encounterMap, b)) {
            throw vstd::task_cancelled();
        }
    };
    const auto requireCompensationCurrent = [requireDefeatCurrent, ownerIsCurrent, expectedGame, initialContext,
                                             initialGeneration, initialEpoch, encounterMap, capturedPlayer, a, b,
                                             winnerClaim, loserClaim] {
        if (ownerIsCurrent()) {
            requireDefeatCurrent();
            return;
        }
        auto capturedGame = expectedGame.lock();
        if (!capturedGame || !initialContext || initialContext->isActive() ||
            initialGeneration == std::numeric_limits<CGameContext::TransitionGeneration>::max() ||
            initialContext->getTransitionGeneration() != initialGeneration + 1 ||
            capturedGame->getContext() != initialContext || capturedGame->getMap() || !capturedPlayer ||
            encounterMap->getAssignedPlayer() != capturedPlayer || capturedGame->getMapBindingEpoch() != initialEpoch ||
            encounterMap->getGame() != capturedGame || a->getGame() != capturedGame || b->getGame() != capturedGame ||
            a->getMap() != encounterMap || b->getMap() != encounterMap || !a->isAlive() || b->isAlive() ||
            !is_registered_on_map(encounterMap, a) || !is_registered_on_map(encounterMap, b) ||
            !b->defeatResolutionInProgress || a->activeDefeatRecipientCount == 0 ||
            a->activeCombatOwner.lock() != winnerClaim || b->activeCombatOwner.lock() != loserClaim) {
            throw vstd::task_cancelled();
        }
    };
    auto admission = encounterMap->tryBeginUnsafeOperation();
    if (!admission) {
        throw vstd::task_cancelled();
    }
    bool workStarted = false;
    bool recoverySettled = false;
    b->defeatResolutionInProgress = true;
    ++a->activeDefeatRecipientCount;
    DefeatScopeExit release([&] {
        b->defeatResolutionInProgress = false;
        --a->activeDefeatRecipientCount;
        if (!workStarted || (recoverySettled && admission->isCurrent())) {
            admission->finish();
        }
    });
    if (!admission->isCurrent()) {
        throw vstd::task_cancelled();
    }
    requireDefeatCurrent();
    workStarted = true;
    b->defeatResolutionUncertain = true;
    const auto winnerDescription = a->to_string();
    requireDefeatCurrent();
    const auto loserDescription = b->to_string();
    requireDefeatCurrent();
    vstd::logger::debug(winnerDescription, a->getName(), "defeated", loserDescription);
    requireDefeatCurrent();
    const bool sevenSunsReplacement =
        CSevenSunsMerchantDialogue::isSettledReplacement(expectedGame.lock(), encounterMap, b, requireDefeatCurrent);
    requireDefeatCurrent();
    if (sevenSunsReplacement) {
        a->addExp(420);
    } else {
        const auto rewardScale = b->getScale();
        requireDefeatCurrent();
        a->addExpScaled(rewardScale);
    }
    requireDefeatCurrent();
    const bool fixedLoot = encounterMap->getBoolProperty("plugin_cityFixedLoot");
    requireDefeatCurrent();
    std::set<std::shared_ptr<CItem>> items;
    if (!fixedLoot) {
        const auto randomLootScale = b->getScale();
        requireDefeatCurrent();
        auto lootRng = initialContext->getDefeatRngHandler(requireDefeatCurrent);
        requireDefeatCurrent();
        items = lootRng->calculateDefeatLoot(randomLootScale, requireDefeatCurrent);
    }
    requireDefeatCurrent();
    auto equipment = b->getEquipped();
    const int ownedGold = fixedLoot && !playerDefeat ? std::max(0, b->getGold()) : 0;
    if (ownedGold) {
        b->setGold(0);
        requireDefeatCurrent();
        a->addGold(ownedGold);
        requireDefeatCurrent();
    }
    std::map<std::string, std::pair<std::string, int>> lostItems;
    auto game = b->getGame();
    const bool showDefeat = playerDefeat && game->getGui() && game->getGui()->findChild("CGameFightPanel");
    requireDefeatCurrent();
    const auto possessions = fixedLoot && !playerDefeat ? b->getAllItems() : b->getInInventory();
    requireDefeatCurrent();
    for (const std::shared_ptr<CItem> &item : possessions) {
        const bool undroppable = fixedLoot && item->getBoolProperty("plugin_cityUndroppable");
        requireDefeatCurrent();
        if (undroppable) {
            continue;
        }
        const bool retainedQuestItem = playerDefeat && item->hasTag(CTag::Quest);
        requireDefeatCurrent();
        if (!retainedQuestItem) {
            b->removeItem(item);
            requireDefeatCurrent();
            if (fixedLoot && !playerDefeat) {
                std::erase_if(equipment, [&item](const auto &slot) { return slot.second == item; });
            }
            items.insert(item);
            if (playerDefeat && !b->hasInInventory(item)) {
                auto &entry = lostItems[item->getTypeId().empty() ? item->getName() : item->getTypeId()];
                entry.first = item->getLabel();
                ++entry.second;
            }
        }
    }
    if (fixedLoot && !playerDefeat && equipment != b->getEquipped()) {
        b->setEquipped(std::move(equipment));
    }
    requireDefeatCurrent();
    if (CPlaytestTrace::enabled()) {
        json fields = {
            {"defeated", CPlaytestTrace::objectRef(b)},
            {"ownedGold", ownedGold},
            {"items", CPlaytestTrace::itemRefs(items)},
            {"recipient", CPlaytestTrace::objectRef(a)},
            {"rewardSource", "combat"},
            {"scale", b->getScale()},
        };
        CPlaytestTrace::addMapContext(fields, encounterMap);
        CPlaytestTrace::record("reward_granted", fields);
    }
    requireDefeatCurrent();
    auto rng = initialContext->getDefeatRngHandler(requireDefeatCurrent);
    requireDefeatCurrent();
    auto context = game->getContext();
    game.reset();
    struct DefeatLootSettlement {
        const std::set<std::shared_ptr<CItem>> owned;
        std::set<std::shared_ptr<CItem>> attempted;
        std::set<std::shared_ptr<CItem>> committed;
        bool uncertain = false;

        explicit DefeatLootSettlement(std::set<std::shared_ptr<CItem>> items) : owned(std::move(items)) {}
        DefeatLootSettlement(const DefeatLootSettlement &) = delete;
        DefeatLootSettlement &operator=(const DefeatLootSettlement &) = delete;
        DefeatLootSettlement(DefeatLootSettlement &&) = delete;
        DefeatLootSettlement &operator=(DefeatLootSettlement &&) = delete;
    };
    auto settlement = std::make_shared<DefeatLootSettlement>(items);
    const auto settleItems = [a, settlement](const std::function<void()> &requireCurrent) {
        if (settlement->uncertain) {
            throw std::logic_error("Defeat loot settlement is uncertain");
        }
        try {
            requireCurrent();
            for (const auto &item : settlement->owned) {
                requireCurrent();
                if (!item || item->getGame() != a->getGame()) {
                    throw std::logic_error("Defeat loot item ownership changed");
                }
                if (settlement->attempted.contains(item)) {
                    if (!settlement->committed.contains(item)) {
                        throw std::logic_error("An attempted defeat loot grant cannot be retried");
                    }
                    if (!a->items.contains(item)) {
                        throw std::logic_error("A committed defeat loot grant was removed");
                    }
                    continue;
                }
                settlement->attempted.insert(item);
                if (!a->items.contains(item)) {
                    a->addItem(item);
                }
                requireCurrent();
                if (!a->items.contains(item)) {
                    throw std::logic_error("Defeat loot was removed during its grant");
                }
                settlement->committed.insert(item);
            }
            for (const auto &item : settlement->owned) {
                requireCurrent();
                if (!settlement->committed.contains(item) || item->getGame() != a->getGame() ||
                    !a->items.contains(item)) {
                    throw std::logic_error("Defeat loot settlement lost an earlier committed item");
                }
            }
            requireCurrent();
        } catch (...) {
            settlement->uncertain = true;
            throw;
        }
    };
    const auto settleCurrent = [settleItems, requireDefeatCurrent] { settleItems(requireDefeatCurrent); };
    const auto compensate = [settleItems, requireCompensationCurrent] { settleItems(requireCompensationCurrent); };

    std::exception_ptr cancellation;
    try {
        co_await rng->addDefeatLootAsync(a, items, requireDefeatCurrent, settleCurrent, compensate);
    } catch (const vstd::task_cancelled &) {
        cancellation = std::current_exception();
        try {
            compensate();
        } catch (...) {
            std::rethrow_exception(cancellation);
        }
        if (!context->isActive()) {
            std::rethrow_exception(cancellation);
        }
    }
    requireDefeatCurrent();
    if (cancellation) {
        auto removal = context->spawnTask(encounterMap->removeObjectAsync(b));
        co_await removal.waitFinished();
        requireOwnerCurrent();
        try {
            removal.get();
        } catch (const vstd::task_cancelled &) {
        }
    } else {
        co_await encounterMap->removeObjectAsync(b);
    }
    requireOwnerCurrent();
    const auto recoveryIsComplete = [&] {
        if (!ownerIsCurrent() || !a->isAlive() || !is_registered_on_map(encounterMap, a)) {
            return false;
        }
        if (playerDefeat) {
            if (capturedPlayer != defeatedPlayer || encounterMap->getAssignedPlayer() != defeatedPlayer) {
                return false;
            }
            if (encounterMap->getPermanentPlayerDeath()) {
                return encounterMap->getDefeatedPlayer() == b && encounterMap->hasRetainedTerminalPlayer();
            }
            return encounterMap->player == b && b->isAlive() && is_registered_on_map(encounterMap, b);
        }
        return std::ranges::none_of(encounterMap->getObjects(), [&](const auto &object) { return object == b; });
    };
    if (!recoveryIsComplete()) {
        throw vstd::task_cancelled();
    }
    if (playerDefeat) {
        json receipt = {
            {"map", encounterMap->getLabel().empty() ? encounterMap->getMapName() : encounterMap->getLabel()},
            {"hp", b->getHp()},
            {"x", b->getPosX()},
            {"y", b->getPosY()},
            {"z", b->getPosZ()},
            {"lostItems", json::array()},
            {"lostItemCount", 0}};
        int count = 0;
        for (const auto &[id, entry] : lostItems) {
            receipt["lostItems"][receipt["lostItems"].size()] = {
                {"id", id}, {"label", entry.first}, {"count", entry.second}};
            count += entry.second;
        }
        receipt["lostItemCount"] = count;
        requireOwnerCurrent();
        b->setStringProperty("uiDefeatReceipt", receipt.dump());
        if (!recoveryIsComplete()) {
            throw vstd::task_cancelled();
        }
        if (showDefeat) {
            game = b->getGame();
            std::weak_ptr<CGame> weakGame = game;
            std::weak_ptr<CMap> weakMap = encounterMap;
            std::weak_ptr<CCreature> weakPlayer = b;
            auto context = game->getContext();
            std::weak_ptr<CGameContext> weakContext = context;
            const auto generation = context->captureTransitionGeneration();
            auto present = [weakGame, weakMap, weakPlayer, weakContext, generation] {
                auto context = weakContext.lock();
                if (context && context->isTransitionGenerationCurrent(generation)) {
                    context->spawnTask(showDefeatOwnedAsync(weakGame, weakMap, weakPlayer, generation));
                }
            };
            if (encounterOwner) {
                if (encounterOwner->defeatPresentation) {
                    throw std::logic_error("An encounter already owns a defeat presentation.");
                }
                encounterOwner->defeatPresentation = std::move(present);
            } else {
                present();
            }
        }
    }
    requireOwnerCurrent();
    if (encounterOwner && !encounterOwner->defeatAdmission) {
        encounterOwner->defeatAdmission.emplace(std::move(*admission));
    }
    recoverySettled = true;
    b->defeatResolutionUncertain = false;
    if (cancellation) {
        std::rethrow_exception(cancellation);
    }
}

void CFightHandler::applyEffects(const std::shared_ptr<CCreature> &cr) { apply_effects_with_result(cr); }
