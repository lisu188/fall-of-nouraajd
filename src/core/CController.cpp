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
#include "core/CController.h"
#include <algorithm>
#include <cstdlib>

#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CMap.h"
#include "core/CNavigation.h"
#include "core/CNavigationFlow.h"
#include "core/CNavigationSearch.h"
#include "gui/panel/CGameFightPanel.h"
#include "object/CMapObject.h"
#include "object/CPlayer.h"

namespace {
struct DeferredCreatureContext {
    std::weak_ptr<CCreature> creature;
    std::weak_ptr<CMap> map;
    std::weak_ptr<CGame> game;
    std::weak_ptr<CGameContext> context;
    CGameContext::TransitionGeneration generation = 0;
    std::string creatureName;
    Coords fallback = ZERO;
    bool hadContext = false;
    bool wasRegistered = false;
};

DeferredCreatureContext capture_deferred_creature_context(const std::shared_ptr<CCreature> &creature) {
    DeferredCreatureContext result;
    result.creature = creature;
    if (!creature) {
        return result;
    }

    result.fallback = creature->getCoords();
    result.creatureName = creature->getName();
    auto map = creature->getMap();
    result.map = map;
    auto game = creature->getGame();
    result.game = game;
    if (game) {
        auto context = game->getContext();
        result.context = context;
        result.generation = context->captureTransitionGeneration();
        result.hadContext = true;
    }
    result.wasRegistered = map && !result.creatureName.empty() && map->getObjectByName(result.creatureName) == creature;
    return result;
}

bool resolve_deferred_creature_context(const DeferredCreatureContext &context, std::shared_ptr<CCreature> &creature,
                                       std::shared_ptr<CMap> &map) {
    creature = context.creature.lock();
    map = context.map.lock();
    if (!creature || !map) {
        return false;
    }

    auto transitionContext = context.context.lock();
    if (context.hadContext &&
        (!transitionContext || !transitionContext->isTransitionGenerationCurrent(context.generation))) {
        return false;
    }

    const bool stillRegistered = context.wasRegistered && !context.creatureName.empty() &&
                                 map->getObjectByName(context.creatureName) == creature;
    auto game = context.game.lock();
    const bool expectedMapActive = !game || game->getMap() == map;
    if (!expectedMapActive && !stillRegistered) {
        return false;
    }
    if (context.wasRegistered && !stillRegistered) {
        return false;
    }
    return true;
}

bool contains_navigation_neighbor(const std::shared_ptr<CMap> &map, Coords from, Coords to) {
    if (!map) {
        return false;
    }
    to = map->normalizeCoords(to);
    auto neighbors = map->getNavigationNeighbors(from);
    return std::ranges::find(neighbors, to) != neighbors.end();
}

bool creature_can_follow_step(const std::shared_ptr<CMap> &map, const std::shared_ptr<CCreature> &creature,
                              const Coords &step) {
    if (!map || !creature) {
        return false;
    }
    auto current = map->normalizeCoords(creature->getCoords());
    auto target = map->normalizeCoords(step);
    return target != current && map->canStep(target) && contains_navigation_neighbor(map, current, target);
}

Coords find_shared_target_next_step(const std::shared_ptr<CMap> &map, const std::shared_ptr<CCreature> &creature,
                                    const std::shared_ptr<CMapObject> &targetObject) {
    if (!map || !creature || !targetObject) {
        return creature ? creature->getCoords() : ZERO;
    }

    auto start = map->normalizeCoords(creature->getCoords());
    auto goal = map->normalizeCoords(targetObject->getCoords());
    if (start == goal || !map->canStep(goal)) {
        return start;
    }

    // Preserve the existing raw-axis chase leash, including on wrapped maps.
    constexpr int maxChaseDistance = 256;
    if (std::abs(static_cast<std::int64_t>(start.x) - goal.x) > maxChaseDistance ||
        std::abs(static_cast<std::int64_t>(start.y) - goal.y) > maxChaseDistance) {
        return start;
    }

    const auto result = map->getNavigationService()->nextStep(map, targetObject, start, goal, map->getTurn());
    if (map->normalizeCoords(creature->getCoords()) != start ||
        map->normalizeCoords(targetObject->getCoords()) != goal) {
        return creature->getCoords();
    }
    if (result.status != CNavigationFlowStatus::Complete) {
        return start;
    }
    auto step = map->normalizeCoords(result.step);
    if (!creature_can_follow_step(map, creature, step)) {
        return start;
    }
    return step;
}
} // namespace

std::size_t performance_guard::targetFlowCacheSize() { return CNavigationService::flowCacheSize(); }

void performance_guard::clearTargetFlowCache() { CNavigationService::clearFlows(); }

CTargetController::CTargetController() {}

std::shared_ptr<vstd::future<Coords, void>> CTargetController::control(std::shared_ptr<CCreature> creature) {
    if (!creature || !creature->getMap()) {
        return vstd::make_ready_future(ZERO);
    }
    auto deferredContext = capture_deferred_creature_context(creature);
    auto sourceMap = deferredContext.map.lock();
    auto target_object = sourceMap ? sourceMap->getObjectByName(target) : nullptr;
    if (!target_object) {
        return vstd::make_ready_future(deferredContext.fallback);
    }
    return vstd::async([deferredContext, target_object]() {
        std::shared_ptr<CCreature> creature;
        std::shared_ptr<CMap> map;
        if (!resolve_deferred_creature_context(deferredContext, creature, map)) {
            return deferredContext.fallback;
        }
        if (!target_object->getName().empty() && map->getObjectByName(target_object->getName()) != target_object) {
            return deferredContext.fallback;
        }
        Coords step;
        try {
            step = find_shared_target_next_step(map, creature, target_object);
        } catch (const std::exception &) {
            if (!resolve_deferred_creature_context(deferredContext, creature, map))
                return deferredContext.fallback;
            throw;
        }
        if (!resolve_deferred_creature_context(deferredContext, creature, map) ||
            (!target_object->getName().empty() && map->getObjectByName(target_object->getName()) != target_object)) {
            return deferredContext.fallback;
        }
        return step;
    });
}

std::shared_ptr<vstd::future<Coords, void>> CController::control(std::shared_ptr<CCreature> c) {
    if (!c) {
        return vstd::make_ready_future(ZERO);
    }
    auto deferredContext = capture_deferred_creature_context(c);
    std::shared_ptr<CCreature> creature;
    std::shared_ptr<CMap> map;
    return vstd::make_ready_future(resolve_deferred_creature_context(deferredContext, creature, map)
                                       ? creature->getCoords()
                                       : deferredContext.fallback);
}

void CController::onStepCommitted(std::shared_ptr<CCreature>, const Coords &) {}

void CController::interrupt(std::shared_ptr<CCreature>) {}

void CController::onTurnEnded(std::shared_ptr<CCreature>) {}

std::string CTargetController::getTarget() { return target; }

void CTargetController::setTarget(std::string target) { this->target = target; }

std::shared_ptr<vstd::future<Coords, void>> CRandomController::control(std::shared_ptr<CCreature> creature) {
    if (!creature) {
        return vstd::make_ready_future(ZERO);
    }
    auto deferredContext = capture_deferred_creature_context(creature);
    std::shared_ptr<CCreature> resolvedCreature;
    std::shared_ptr<CMap> map;
    if (!resolve_deferred_creature_context(deferredContext, resolvedCreature, map)) {
        return vstd::make_ready_future(deferredContext.fallback);
    }
    Coords target = resolvedCreature->getCoords() + Coords(vstd::rand(-1, 1), vstd::rand(-1, 1), 0);
    return vstd::make_ready_future(map->normalizeCoords(target));
}

struct CNpcRandomController::NpcRoute {
    explicit NpcRoute(const std::shared_ptr<CNavigationBudget> &budget)
        : allocationBudget(budget), steps(budget.get()) {}

    std::shared_ptr<CNavigationBudget> allocationBudget;
    std::pmr::vector<Coords> steps;
    std::weak_ptr<CCreature> creature;
    std::weak_ptr<CMap> map;
    std::weak_ptr<CGameContext> context;
    std::uint64_t generation = 0;
    bool hadContext = false;
    bool wasRegistered = false;
    bool wasInstalled = false;
    std::weak_ptr<CController> installedController;
    Coords origin;
};

std::shared_ptr<vstd::future<Coords, void>> CNpcRandomController::control(std::shared_ptr<CCreature> creature) {
    if (!creature || !creature->getMap()) {
        interrupt(creature);
        return vstd::make_ready_future(creature ? creature->getCoords() : ZERO);
    }
    auto deferredContext = capture_deferred_creature_context(creature);
    std::shared_ptr<CMap> map;
    if (!resolve_deferred_creature_context(deferredContext, creature, map)) {
        interrupt(creature);
        return vstd::make_ready_future(deferredContext.fallback);
    }
    if (route) {
        if (currentStep >= route->steps.size()) {
            interrupt(creature);
            return vstd::make_ready_future(creature->getCoords());
        }
        const auto expectedOrigin = currentStep ? route->steps[currentStep - 1] : route->origin;
        const auto context = route->context.lock();
        const bool staleContext =
            route->hadContext && (!context || !context->isTransitionGenerationCurrent(route->generation) ||
                                  !creature->getGame() || creature->getGame()->getContext() != context);
        if (staleContext || route->creature.lock() != creature || route->map.lock() != map ||
            (route->wasRegistered && map->getObjectByName(creature->getName()) != creature) ||
            creature->getCoords() != expectedOrigin ||
            (route->wasInstalled && creature->getController() != route->installedController.lock())) {
            interrupt(creature);
            return vstd::make_ready_future(creature->getCoords());
        }
        const auto next = map->normalizeCoords(route->steps[currentStep]);
        if (creature_can_follow_step(map, creature, next))
            return vstd::make_ready_future(next);
        interrupt(creature);
        return vstd::make_ready_future(creature->getCoords());
    }

    for (int i = 0; i < 10; i++) {
        const auto dx = vstd::rand(-5, 5);
        const auto dy = vstd::rand(-5, 5);
        const auto candidate = map->normalizeCoords(creature->getCoords() + Coords(dx, dy, 0));
        if (!map->canStep(candidate))
            continue;
        auto result = map->getNavigationService()->findPathResult(map, creature->getCoords(), candidate);
        if (result.status == CNavigationSearchStatus::Found && !result.path.empty() &&
            result.path.front() != creature->getCoords()) {
            try {
                auto budget = result.allocationBudget;
                route = std::allocate_shared<NpcRoute>(CNavigationAllocator<NpcRoute>(budget), budget);
                route->steps = std::move(result.path);
                route->creature = creature;
                route->map = map;
                route->context = deferredContext.context;
                route->generation = deferredContext.generation;
                route->hadContext = deferredContext.hadContext;
                route->wasRegistered = deferredContext.wasRegistered;
                const auto installedController = creature->getController();
                route->wasInstalled = installedController.get() == this;
                if (route->wasInstalled)
                    route->installedController = installedController;
                route->origin = creature->getCoords();
                currentStep = 0;
            } catch (const std::bad_alloc &) {
                interrupt(creature);
            }
        }
        break;
    }

    if (route) {
        const auto next = map->normalizeCoords(route->steps[currentStep]);
        if (creature_can_follow_step(map, creature, next))
            return vstd::make_ready_future(next);
        interrupt(creature);
    }

    return vstd::make_ready_future(creature->getCoords());
}

void CNpcRandomController::onStepCommitted(std::shared_ptr<CCreature> creature, const Coords &coords) {
    if (!route || currentStep >= route->steps.size() || route->steps[currentStep] != coords ||
        ++currentStep == route->steps.size())
        interrupt(creature);
}

void CNpcRandomController::interrupt(std::shared_ptr<CCreature>) {
    route.reset();
    currentStep = 0;
}

std::string CGroundController::getTileType() { return _tileType; }

void CGroundController::setTileType(std::string type) { _tileType = type; }

std::shared_ptr<vstd::future<Coords, void>> CGroundController::control(std::shared_ptr<CCreature> creature) {
    auto self = this->ptr<CGroundController>();
    if (!creature || !creature->getMap()) {
        return vstd::make_ready_future(creature ? creature->getCoords() : ZERO);
    }
    auto deferredContext = capture_deferred_creature_context(creature);
    std::shared_ptr<CMap> map;
    if (!resolve_deferred_creature_context(deferredContext, creature, map)) {
        return vstd::make_ready_future(deferredContext.fallback);
    }
    std::vector<Coords> possible;
    for (auto c : map->getAdjacentCoords(creature->getCoords(), true)) {
        std::string type = map->getTile(c)->getTileType();
        if (type == self->getTileType() && map->canStep(c)) {
            possible.push_back(c);
        }
    }
    if (!possible.empty()) {
        return vstd::make_ready_future(*vstd::random_element(possible));
    }
    return vstd::make_ready_future(creature->getCoords());
}

CRangeController::CRangeController() {}

std::shared_ptr<vstd::future<Coords, void>> CRangeController::control(std::shared_ptr<CCreature> creature) {
    auto self = this->ptr<CRangeController>();
    if (!creature || !creature->getMap()) {
        return vstd::make_ready_future(creature ? creature->getCoords() : ZERO);
    }
    auto deferredContext = capture_deferred_creature_context(creature);
    std::shared_ptr<CMap> map;
    if (!resolve_deferred_creature_context(deferredContext, creature, map)) {
        return vstd::make_ready_future(deferredContext.fallback);
    }
    std::vector<Coords> possible;
    std::shared_ptr<CMapObject> targetObject = map->getObjectByName(self->getTarget());
    for (auto c : map->getAdjacentCoords(creature->getCoords(), true)) {
        if ((!targetObject || map->getDistance(targetObject->getCoords(), c) < self->distance) && map->canStep(c)) {
            possible.push_back(c);
        }
    }
    if (!possible.empty()) {
        return vstd::make_ready_future(*vstd::random_element(possible));
    }
    return vstd::make_ready_future(creature->getCoords());
}

std::string CRangeController::getTarget() { return target; }

void CRangeController::setTarget(std::string target) { this->target = target; }

void CRangeController::setDistance(int distance) { this->distance = distance; }

int CRangeController::getDistance() { return distance; }

namespace {
// Deterministic, pessimistic estimate of one landed opponent hit: the top of the
// damage range plus the flat damage bonus (CCreature::getDmg() without the
// miss/crit dice), mitigated by normal resist and armor exactly the way
// CCreature::hurt()/takeDamage() mitigate a normal-damage strike. Block is a
// dice roll and is deliberately not credited, keeping the estimate stable and
// erring toward survival.
int expected_incoming_hit(const std::shared_ptr<CCreature> &me, const std::shared_ptr<CCreature> &opponent) {
    auto attack = opponent->getStats();
    const int raw = std::max(std::max(attack->getDmgMin(), attack->getDmgMax()), 0) + std::max(attack->getDamage(), 0);
    auto defense = me->getStats();
    const int afterResist = raw * (100 - defense->getNormalResist()) / 100.0;
    const int afterArmor = afterResist * ((100 - defense->getArmor()) / 100.0);
    return std::max(afterArmor, 0);
}

// Heal items restore getPower() * 20% of max hp (res/plugins/potion.py), capped
// by the hp actually missing. Returns the estimate for the strongest heal item
// carried, i.e. the best single-turn hp swing a heal turn could buy.
// Estimates how much the heal potion the AI would actually drink restores. The
// controller spends the LEAST powerful heal first (getLeastPowerfulItemWithTag), so the
// gate must weigh that same potion: weighing the strongest would green-light a heal the
// drunk potion cannot keep pace with, re-introducing net-loss chain-drinking.
int consumed_heal_estimate(const std::shared_ptr<CCreature> &me) {
    bool found = false;
    int weakestPower = 0;
    for (const auto &item : me->getItems()) {
        if (item && item->hasTag(CTag::Heal)) {
            const int power = item->getPower();
            if (!found || power < weakestPower) {
                weakestPower = power;
                found = true;
            }
        }
    }
    const int uncapped = weakestPower * me->getHpMax() / 5;
    return std::min(uncapped, me->getHpMax() - me->getHp());
}

// A heal turn is only worth its tempo when it actually preserves the combatant:
// either the creature would not survive the next landed hit anyway (a heal is
// the only move with a chance to keep it alive), or the strongest heal carried
// restores more hp than that hit removes (net gain). Healing reflexively at a
// fixed hp threshold made monsters chain-drink potions against hard hitters
// while losing more hp per turn than each potion restored.
bool heal_preserves_combatant(const std::shared_ptr<CCreature> &me, const std::shared_ptr<CCreature> &opponent) {
    const int incoming = expected_incoming_hit(me, opponent);
    if (me->getHp() <= incoming) {
        return true;
    }
    return consumed_heal_estimate(me) > incoming;
}

// Deterministic estimate of how much a single cast weakens the opponent, used to
// rank a caster's interactions. Every castable interaction is credited with the
// caster's expected landed hit on the opponent (expected_incoming_hit in the
// attacking direction: caster's top damage plus flat bonus, mitigated by the
// opponent's normal resist and armor, with the block dice deliberately excluded
// so the estimate stays stable). An interaction that also routes a non-buff
// effect onto the opponent keeps weakening it for the effect's whole duration,
// so credit that hit once more per lingering turn. Mana cost is intentionally
// not part of the value: the previous selector maximized mana cost, which made
// casters spend their priciest spell instead of their most weakening one.
int weakening_estimate(const std::shared_ptr<CInteraction> &interaction, const std::shared_ptr<CCreature> &me,
                       const std::shared_ptr<CCreature> &opponent) {
    const int hit = expected_incoming_hit(opponent, me);
    int value = hit;
    const auto effect = interaction->getEffect();
    if (effect && !interaction->effectRoutesToCaster(effect) && !effect->hasTag(CTag::Buff)) {
        // A lingering debuff/stun weakens even a caster with no melee damage, so
        // floor the per-turn value at 1 to keep such effects ranked above an
        // interaction that merely lands the same hit once.
        value += std::max(hit, 1) * std::max(effect->getDuration(), 1);
    }
    return value;
}

// Two effects denote the same buff/heal when they share a stable identity: the
// configured typeId when present, otherwise the object name. Monster AI uses this
// to recognize a self-target action whose effect the caster already carries so it
// does not recast it.
bool same_effect_identity(const std::shared_ptr<CEffect> &a, const std::shared_ptr<CEffect> &b) {
    if (!a || !b) {
        return false;
    }
    const std::string aType = a->getTypeId();
    const std::string bType = b->getTypeId();
    if (!aType.empty() || !bType.empty()) {
        return aType == bType;
    }
    return a->getName() == b->getName();
}

// True when the caster already carries an effect with the same identity as the
// one an interaction would apply, i.e. recasting it would only spam a duplicate.
bool caster_already_has_effect(const std::shared_ptr<CCreature> &me, const std::shared_ptr<CEffect> &effect) {
    for (const auto &active : me->getEffects()) {
        if (same_effect_identity(active, effect)) {
            return true;
        }
    }
    return false;
}
} // namespace

bool CMonsterFightController::control(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) {
    if (!me || !opponent) {
        return false;
    }
    if (me->getHpRatio() < 75 && heal_preserves_combatant(me, opponent)) {
        auto object = getLeastPowerfulItemWithTag(me, CTag::Heal);
        if (object) {
            me->useItem(object);
            return true;
        }
    }
    if (me->getManaRatio() < 75) {
        auto object = getLeastPowerfulItemWithTag(me, CTag::Mana);
        if (object) {
            me->useItem(object);
            return true;
        }
    }
    if (auto action = selectInteraction(me, opponent)) {
        me->useAction(action, opponent);
        return true;
    }
    return false;
}

std::shared_ptr<CItem> CMonsterFightController::getLeastPowerfulItemWithTag(std::shared_ptr<CCreature> cr, CTag tag) {
    auto cmp = [](const std::shared_ptr<CItem> &a, const std::shared_ptr<CItem> &b) {
        return a->getPower() < b->getPower();
    };
    std::function<bool(std::shared_ptr<CItem>)> pred = [tag](const std::shared_ptr<CItem> &it) {
        return it->hasTag(tag);
    };
    std::set<std::shared_ptr<CItem>> items = cr->getItems();
    auto rng = items | std::views::filter(pred);
    auto max = std::ranges::min_element(rng, cmp);
    if (max != std::ranges::end(rng)) {
        return *max;
    }
    return {};
}

// Before ranking offensive casts, look for a self-target defensive/heal/buff action
// worth a turn: it must be affordable, route its effect to the caster, and not merely
// duplicate an effect the caster already carries. A Heal-tagged effect only earns the
// turn while the caster is hurt (HpRatio < 75); any other self-routing effect (a buff)
// is worth casting whenever it is missing. This lets monsters shore themselves up
// without spamming duplicate buffs, and otherwise falls through to offensive selection.
std::shared_ptr<CInteraction> CMonsterFightController::selectInteraction(std::shared_ptr<CCreature> me,
                                                                         std::shared_ptr<CCreature> opponent) {
    auto selfTargetUseful = [me](const std::shared_ptr<CInteraction> &it) {
        if (it->getManaCost() > me->getMana()) {
            return false;
        }
        const auto effect = it->getEffect();
        if (!effect || !it->effectRoutesToCaster(effect)) {
            return false;
        }
        if (caster_already_has_effect(me, effect)) {
            return false;
        }
        if (effect->hasTag(CTag::Heal)) {
            return me->getHpRatio() < 75;
        }
        return true;
    };
    // Rank useful self-target actions deterministically: a needed heal outranks a plain
    // buff, then the pricier action wins, then the lexicographically smaller name breaks
    // the tie -- mirroring the offensive selector so container order never decides.
    auto selfPred = [](const std::shared_ptr<CInteraction> &a, const std::shared_ptr<CInteraction> &b) {
        const bool ha = a->getEffect() && a->getEffect()->hasTag(CTag::Heal);
        const bool hb = b->getEffect() && b->getEffect()->hasTag(CTag::Heal);
        if (ha != hb) {
            return !ha;
        }
        if (a->getManaCost() != b->getManaCost()) {
            return a->getManaCost() < b->getManaCost();
        }
        return a->getName() > b->getName();
    };
    std::set<std::shared_ptr<CInteraction>> selfInteractions = me->getInteractions();
    auto selfRng = selfInteractions | std::views::filter(selfTargetUseful);
    auto bestSelf = std::ranges::max_element(selfRng, selfPred);
    if (bestSelf != std::ranges::end(selfRng)) {
        return *bestSelf;
    }

    std::function<bool(std::shared_ptr<CInteraction>)> pFunction = [](const std::shared_ptr<CInteraction> &it) {
        return !it->hasTag(CTag::Buff);
    };
    std::function<bool(std::shared_ptr<CInteraction>)> pFunction2 = [me](const std::shared_ptr<CInteraction> &it) {
        return it->getManaCost() <= me->getMana();
    };
    // Exclude every self-routing interaction (a Buff-tagged effect or an explicit selfTarget) from
    // offensive selection: those are handled by the self-target pass above, so a self-heal or self-buff
    // never leaks into the offensive ranking (where, crediting only its incidental hit, it could tie a
    // pure attack and win the cheaper-cost tie-break).
    std::function<bool(std::shared_ptr<CInteraction>)> pFunction3 = [](const std::shared_ptr<CInteraction> &it) {
        const auto effect = it->getEffect();
        return !effect || !it->effectRoutesToCaster(effect);
    };
    // Rank affordable, non-buff interactions by how much they weaken the current
    // opponent rather than by mana cost. Ties break toward the cheaper spell, then
    // by name, so the choice is deterministic regardless of container ordering.
    auto pred = [me, opponent](const std::shared_ptr<CInteraction> &a, const std::shared_ptr<CInteraction> &b) {
        const int wa = weakening_estimate(a, me, opponent);
        const int wb = weakening_estimate(b, me, opponent);
        if (wa != wb) {
            return wa < wb;
        }
        if (a->getManaCost() != b->getManaCost()) {
            return a->getManaCost() > b->getManaCost();
        }
        return a->getName() > b->getName();
    };
    std::set<std::shared_ptr<CInteraction>> interactions = me->getInteractions();
    auto rng =
        interactions | std::views::filter(pFunction) | std::views::filter(pFunction2) | std::views::filter(pFunction3);
    auto max = std::ranges::max_element(rng, pred);
    if (max != std::ranges::end(rng)) {
        return *max;
    }
    return {};
}

struct CPlayerController::PlayerRoute {
    explicit PlayerRoute(const std::shared_ptr<CNavigationBudget> &budget)
        : allocationBudget(budget), steps(budget.get()), nextOccurrence(budget.get()), firstRemaining(budget.get()) {}

    std::shared_ptr<CNavigationBudget> allocationBudget;
    std::pmr::vector<Coords> steps;
    std::pmr::vector<std::size_t> nextOccurrence;
    std::pmr::unordered_map<Coords, std::size_t, CNavigationCoordsHash> firstRemaining;
    std::weak_ptr<CMap> map;
    std::weak_ptr<CPlayer> player;
    std::weak_ptr<CGameContext> context;
    std::uint64_t generation = 0;
    bool hadContext = false;
    Coords origin;
};

std::shared_ptr<vstd::future<Coords, void>> CPlayerController::control(std::shared_ptr<CCreature> c) {
    auto player = vstd::cast<CPlayer>(c);
    if (!player) {
        return vstd::now([]() { return ZERO; });
    }
    return vstd::now([this, player]() {
        if (!canContinue(player)) {
            // A path that can no longer be continued (finished, or its next step became blocked)
            // is abandoned outright, so a later poll cannot silently resume a stale route after
            // the obstacle moves away.
            clearPath();
            return player->getCoords();
        }
        return route->steps.at(currentStep);
    });
}

void CPlayerController::setTarget(std::shared_ptr<CPlayer> player, Coords _target) {
    clearPath();
    if (!player || !player->getMap()) {
        return;
    }
    auto map = player->getMap();
    auto normalized = map->normalizeCoords(_target);
    if (!map->isWithinBounds(normalized)) {
        return;
    }
    target = normalized;
    auto result = calculatePath(player);
    if (result.status != CNavigationSearchStatus::Found || result.path.empty() || result.path.back() != normalized ||
        result.path.front() == player->getCoords()) {
        target.reset();
        return;
    }
    try {
        auto budget = result.allocationBudget;
        route = std::allocate_shared<PlayerRoute>(CNavigationAllocator<PlayerRoute>(budget), budget);
        route->steps = std::move(result.path);
        const auto &steps = route->steps;
        route->nextOccurrence.resize(steps.size(), std::numeric_limits<std::size_t>::max());
        route->firstRemaining.reserve(steps.size());
        for (std::size_t index = steps.size(); index-- > 0;) {
            auto [entry, inserted] = route->firstRemaining.try_emplace(steps[index], index);
            if (!inserted) {
                route->nextOccurrence[index] = entry->second;
                entry->second = index;
            }
        }
        route->map = map;
        route->player = player;
        route->origin = player->getCoords();
        if (auto game = player->getGame()) {
            route->context = game->getContext();
            route->generation = game->getContext()->captureTransitionGeneration();
            route->hadContext = true;
        }
    } catch (const std::bad_alloc &) {
        clearPath();
    }
}

void CPlayerController::onStepCommitted(std::shared_ptr<CCreature>, const Coords &coords) {
    if (route && currentStep < route->steps.size() && route->steps[currentStep] == coords) {
        currentStep++;
        if (currentStep == route->steps.size()) {
            clearPath();
        } else if (currentStep > 1) {
            const auto previous = currentStep - 2;
            const auto next = route->nextOccurrence[previous];
            if (next == std::numeric_limits<std::size_t>::max())
                route->firstRemaining.erase(route->steps[previous]);
            else
                route->firstRemaining[route->steps[previous]] = next;
        }
    } else {
        clearPath();
    }
}

void CPlayerController::interrupt(std::shared_ptr<CCreature>) { clearPath(); }

void CPlayerController::onTurnEnded(std::shared_ptr<CCreature>) {}

std::pair<bool, Coords::Direction> CPlayerController::isOnPath(std::shared_ptr<CPlayer> player, Coords coords) {
    if (!isCompleted(player)) {
        ++overlayLookupCount;
        const auto found = route->firstRemaining.find(player->getMap()->normalizeCoords(coords));
        if (found != route->firstRemaining.end()) {
            const auto index = found->second;
            const auto previous = index ? route->steps[index - 1] : route->origin;
            const auto direction = player->getMap()->getShortestDelta(previous, route->steps[index]);
            return std::make_pair(true, CUtil::getDirection(direction));
        }
    }
    return std::make_pair(false, Coords::Direction::ZERO);
}

bool CPlayerController::isCompleted(std::shared_ptr<CPlayer> player) {
    if (hasPendingPath(player))
        return false;
    if (route || target)
        clearPath();
    return true;
}

void CPlayerController::clearPath() {
    ++requestSerial;
    target.reset();
    route.reset();
    currentStep = 0;
}

std::uint64_t CPlayerController::getRequestSerial() const { return requestSerial; }

std::uint64_t CPlayerController::getOverlayLookupCount() const { return overlayLookupCount; }

bool CPlayerController::hasPendingPath(std::shared_ptr<CPlayer> player) {
    if (!target || !route || !player || !player->getMap() || currentStep >= route->steps.size()) {
        return false;
    }
    auto map = player->getMap();
    if (route->map.lock() != map || route->player.lock() != player)
        return false;
    if (route->hadContext) {
        const auto context = route->context.lock();
        if (!context || !player->getGame() || player->getGame()->getContext() != context ||
            !context->isTransitionGenerationCurrent(route->generation))
            return false;
    }
    const auto expectedOrigin = currentStep ? route->steps[currentStep - 1] : route->origin;
    if (player->getCoords() != expectedOrigin)
        return false;
    auto normalized_target = map->normalizeCoords(*target);
    if (player->getCoords() == normalized_target || !map->canStep(normalized_target)) {
        return false;
    }
    auto next = map->normalizeCoords(route->steps[currentStep]);
    return next != player->getCoords() && map->canStep(next) &&
           contains_navigation_neighbor(map, player->getCoords(), next);
}

bool CPlayerController::canContinue(std::shared_ptr<CPlayer> player) { return hasPendingPath(player); }

CNavigationSearchResult CPlayerController::calculatePath(std::shared_ptr<CPlayer> player) {
    auto map = player->getMap();
    return map->getNavigationService()->findPathResult(map, player->getCoords(), *target);
}

bool CFightController::control(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) {
    if (!me || !opponent) {
        return false;
    }
    vstd::logger::warning("Empty fight controller used!");
    return true;
}

void CFightController::start(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) {}

void CFightController::end(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) {}

bool CFightController::isCancelled(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) { return false; }

void CFightController::setOpponents(std::shared_ptr<CCreature> me,
                                    const std::vector<std::shared_ptr<CCreature>> &opponents) {}

std::shared_ptr<CCreature> CFightController::selectOpponent(std::shared_ptr<CCreature> me,
                                                            const std::vector<std::shared_ptr<CCreature>> &opponents,
                                                            std::shared_ptr<CCreature> opponent) {
    auto current = std::find(opponents.begin(), opponents.end(), opponent);
    if (current != opponents.end()) {
        return *current;
    }
    return opponents.empty() ? std::shared_ptr<CCreature>() : opponents.front();
}

void CPlayerFightController::start(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) {
    cancelled = false;
    // Discard any stale panel through its teardown path so its children are removed
    // from CGui instead of leaking when the shared_ptr is overwritten below.
    if (fightPanel) {
        fightPanel->close();
        fightPanel = nullptr;
    }
    encounterMap.reset();
    controlledCreature.reset();
    encounterGeneration = 0;
    hasEncounterGeneration = false;
    if (!me || !opponent || !me->getMap() || !me->getMap()->getGame()) {
        cancelled = true;
        return;
    }
    auto map = me->getMap();
    // Refuse to bind a panel to an opponent that is not present on the encounter map.
    // Use the same runtime-identity presence semantics the engine uses for combat
    // participants (CCreature step-combat predicate / CFightHandler is_registered_on_map);
    // a strict shared_ptr/game-map equality check would reject legitimate engine-initiated
    // fights (e.g. restored instances after save-load, or combat that resolves on the
    // source map while a scene transition to a new game map is pending).
    if (!CGameObject::sameRuntimeIdentity(map->getObjectByName(opponent->getName()), opponent)) {
        cancelled = true;
        return;
    }
    auto gui = map->getGame()->getGui();
    if (!gui) {
        cancelled = true;
        return;
    }
    encounterMap = map;
    controlledCreature = me;
    auto context = map->getGame()->getContext();
    encounterGeneration = context->captureTransitionGeneration();
    hasEncounterGeneration = true;
    fightPanel = me->getGame()->createObject<CGameFightPanel>("fightPanel");
    fightPanel->resetCancellation();
    fightPanel->setEnemies({opponent});
    gui->pushChild(fightPanel);
}

bool CPlayerFightController::control(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) {
    if (!me || !opponent || !me->getMap() || !me->getMap()->getGame()) {
        cancelled = true;
        return false;
    }
    if (hasCancelledContext(me)) {
        cancelled = true;
        return false;
    }
    bool used = false;
    auto gui = me->getMap()->getGame()->getGui();
    if (!gui) {
        cancelled = true;
        return false;
    }

    // TODO: what about mana cost?
    auto target = fightPanel && fightPanel->getEnemy() ? fightPanel->getEnemy() : opponent;
    if (fightPanel && target) {
        auto action = fightPanel->selectInteraction();
        if (fightPanel->isCancelled() || hasCancelledContext(me)) {
            cancelled = true;
            return false;
        }
        if (action) {
            me->useAction(action, target);
            used = true;
        }
    } else {
        cancelled = true;
    }
    return used;
}

void CPlayerFightController::end(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) {
    // Idempotent teardown: an already-closed/absent panel is a clean no-op.
    auto panel = fightPanel;
    fightPanel = nullptr;
    if (!panel) {
        return;
    }
    // close() detaches the panel from CGui through its own parent chain (getTopParent),
    // not through me/opponent/map, so it stays safe when the player is gone, the map
    // object was removed, the GUI was destroyed, or the active map has advanced past the
    // encounter (the same staleness hasCancelledContext()/the deferred guards tolerate).
    // Clearing fightPanel before this call keeps the member null on every path, including
    // if close() throws.
    panel->close();
}

bool CPlayerFightController::isCancelled(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) {
    if (cancelled || hasCancelledContext(me)) {
        cancelled = true;
        return true;
    }
    return false;
}

void CPlayerFightController::setOpponents(std::shared_ptr<CCreature> me,
                                          const std::vector<std::shared_ptr<CCreature>> &opponents) {
    if (fightPanel && !opponents.empty()) {
        fightPanel->setEnemies(opponents);
    }
}

std::shared_ptr<CCreature>
CPlayerFightController::selectOpponent(std::shared_ptr<CCreature> me,
                                       const std::vector<std::shared_ptr<CCreature>> &opponents,
                                       std::shared_ptr<CCreature> opponent) {
    setOpponents(me, opponents);
    if (fightPanel && fightPanel->getEnemy()) {
        return fightPanel->getEnemy();
    }
    return CFightController::selectOpponent(me, opponents, opponent);
}

bool CPlayerFightController::hasCancelledContext(std::shared_ptr<CCreature> me) {
    auto startedMap = encounterMap.lock();
    auto controlled = controlledCreature.lock();
    if (!me || !startedMap || !controlled || controlled != me || me->getMap() != startedMap ||
        startedMap->getObjectByName(me->getName()) != me) {
        return true;
    }

    auto game = me->getGame();
    if (!game || game->getMap() != startedMap) {
        return true;
    }
    auto context = game->getContext();
    if (hasEncounterGeneration && (!context || !context->isTransitionGenerationCurrent(encounterGeneration))) {
        return true;
    }

    auto gui = game->getGui();
    return !gui || !fightPanel || fightPanel->isCancelled() || gui->findChild(fightPanel) == nullptr;
}
