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
#include "gui/panel/CGameFightPanel.h"
#include "object/CMapObject.h"
#include "object/CPlayer.h"

namespace {
constexpr std::size_t MAX_FLOW_FIELD_CELLS = 1'000'000;

struct FlowQueueNode {
    int cost;
    Coords coords;
};

struct FlowQueueCompare {
    bool operator()(const FlowQueueNode &a, const FlowQueueNode &b) const { return a.cost > b.cost; }
};

struct TargetFlowField {
    std::weak_ptr<CMap> map;
    std::uint64_t revision = 0;
    Coords goal;
    std::unordered_map<Coords, Coords> nextSteps;
    // Incremental Dijkstra state: the flood from `goal` is extended lazily, only far
    // enough to settle each requesting creature's start cell, so a single chaser on a
    // huge map never pays for flooding the whole map. `frontier`/`costs` persist so a
    // later, farther request resumes the same search instead of rebuilding.
    std::unordered_map<Coords, int> costs;
    std::priority_queue<FlowQueueNode, std::vector<FlowQueueNode>, FlowQueueCompare> frontier;
    bool exhausted = false;
};

std::mutex targetFlowMutex;
std::vector<std::shared_ptr<TargetFlowField>> targetFlowCache;

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

void add_unique_candidate(const std::shared_ptr<CMap> &map, std::vector<Coords> &candidates, Coords candidate) {
    candidate = map->normalizeCoords(candidate);
    if (std::ranges::find(candidates, candidate) == candidates.end()) {
        candidates.push_back(candidate);
    }
}

std::vector<Coords> get_reverse_navigation_neighbors(const std::shared_ptr<CMap> &map, Coords coords) {
    coords = map->normalizeCoords(coords);
    auto candidates = map->getNavigationNeighbors(coords);
    if (map->getNavigationEdges().empty()) {
        return candidates;
    }

    for (const auto &edge : map->getNavigationEdges()) {
        if (!edge.enabled) {
            continue;
        }
        if (edge.target == coords) {
            add_unique_candidate(map, candidates, edge.source);
        }
        if (edge.bidirectional && edge.source == coords) {
            add_unique_candidate(map, candidates, edge.target);
        }
    }

    std::vector<Coords> reachable;
    for (auto candidate : candidates) {
        candidate = map->normalizeCoords(candidate);
        if (candidate != coords && contains_navigation_neighbor(map, candidate, coords)) {
            add_unique_candidate(map, reachable, candidate);
        }
    }
    return reachable;
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

int movement_step_cost(const std::shared_ptr<CMap> &map, const Coords &, const Coords &to) {
    return map ? map->lookupMovementCost(to) : 1;
}

std::shared_ptr<TargetFlowField> seed_target_flow_field(const std::shared_ptr<CMap> &map, const Coords &goal,
                                                        std::uint64_t revision) {
    auto field = std::make_shared<TargetFlowField>();
    field->map = map;
    field->revision = revision;
    field->goal = goal;

    if (!map->canStep(goal)) {
        field->exhausted = true;
        return field;
    }

    field->costs[goal] = 0;
    field->frontier.push({0, goal});
    return field;
}

// Extends the flood until `start` is settled (or the search is exhausted, or the
// per-call work budget runs out). With positive step costs Dijkstra pops in
// nondecreasing cost order, so once the cheapest frontier entry costs at least as
// much as the best known cost for `start`, no future relaxation can improve
// `start` and its nextStep is final. The unpopped frontier stays in the field so
// a later, farther request resumes where this one stopped. The per-call budget
// bounds the work a single chase step can trigger on huge maps (a 1000x1000 map
// would otherwise flood up to a million cells inside one map turn); a chaser
// whose start was not reached within budget follows its best-known step or
// stalls for the turn, and the resumed search covers more cells on later calls.
void extend_target_flow_field(const std::shared_ptr<TargetFlowField> &field, const std::shared_ptr<CMap> &map,
                              const Coords &start) {
    constexpr std::size_t maxExpansionsPerCall = 25'000;
    std::size_t expansions = 0;
    while (!field->exhausted && !field->frontier.empty()) {
        auto settled = field->costs.find(start);
        if (settled != field->costs.end() && field->frontier.top().cost >= settled->second) {
            return;
        }
        if (field->costs.size() >= MAX_FLOW_FIELD_CELLS) {
            vstd::logger::warning("Target flow field reached visit limit");
            field->exhausted = true;
            return;
        }
        if (++expansions > maxExpansionsPerCall) {
            vstd::logger::debug("Target flow field expansion budget reached before settling requested start");
            return;
        }
        auto current = field->frontier.top();
        field->frontier.pop();

        auto best = field->costs.find(current.coords);
        if (best == field->costs.end() || best->second != current.cost) {
            continue;
        }

        for (auto previous : get_reverse_navigation_neighbors(map, current.coords)) {
            if (previous != field->goal && !map->canStep(previous)) {
                continue;
            }

            const int nextCost = current.cost + movement_step_cost(map, previous, current.coords);
            auto previousCost = field->costs.find(previous);
            if (previousCost == field->costs.end() || nextCost < previousCost->second) {
                field->costs[previous] = nextCost;
                field->nextSteps[previous] = current.coords;
                field->frontier.push({nextCost, previous});
            }
        }
    }
    if (field->frontier.empty()) {
        field->exhausted = true;
    }
}

std::shared_ptr<TargetFlowField> get_target_flow_field(const std::shared_ptr<CMap> &map, const Coords &goal,
                                                       const Coords &start) {
    constexpr std::size_t maxCachedFlowFields = 32;
    const auto revision = map->getNavigationRevision();
    std::lock_guard<std::mutex> lock(targetFlowMutex);

    targetFlowCache.erase(std::remove_if(targetFlowCache.begin(), targetFlowCache.end(),
                                         [](const auto &field) { return !field || field->map.expired(); }),
                          targetFlowCache.end());

    auto cached = std::find_if(targetFlowCache.begin(), targetFlowCache.end(), [&](const auto &field) {
        return field->map.lock() == map && field->revision == revision && field->goal == goal;
    });

    std::shared_ptr<TargetFlowField> field;
    if (cached != targetFlowCache.end()) {
        field = *cached;
    } else {
        field = seed_target_flow_field(map, goal, revision);
        targetFlowCache.push_back(field);
        while (targetFlowCache.size() > maxCachedFlowFields) {
            targetFlowCache.erase(targetFlowCache.begin());
        }
    }
    extend_target_flow_field(field, map, start);
    return field;
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

    // Chase leash: a chaser farther than this from its target holds position instead of
    // flooding the navigation field toward it. Every authored map before the 1000x1000
    // world maps fits inside the leash (200x200 tops), so their behavior is unchanged;
    // on huge maps this bounds the per-turn navigation cost that made a single map turn
    // take tens of seconds in CI.
    constexpr int maxChaseDistance = 256;
    if (std::abs(start.x - goal.x) > maxChaseDistance || std::abs(start.y - goal.y) > maxChaseDistance) {
        return start;
    }

    auto flow = get_target_flow_field(map, goal, start);
    auto next = flow->nextSteps.find(start);
    if (next == flow->nextSteps.end()) {
        return start;
    }
    auto step = map->normalizeCoords(next->second);
    if (!creature_can_follow_step(map, creature, step)) {
        return start;
    }
    return step;
}
} // namespace

std::size_t performance_guard::targetFlowCacheSize() {
    std::lock_guard<std::mutex> lock(targetFlowMutex);
    targetFlowCache.erase(std::remove_if(targetFlowCache.begin(), targetFlowCache.end(),
                                         [](const auto &field) { return !field || field->map.expired(); }),
                          targetFlowCache.end());
    return targetFlowCache.size();
}

void performance_guard::clearTargetFlowCache() {
    std::lock_guard<std::mutex> lock(targetFlowMutex);
    targetFlowCache.clear();
}

CTargetController::CTargetController() {}

std::shared_ptr<vstd::future<Coords, void>> CTargetController::control(std::shared_ptr<CCreature> creature) {
    if (!creature || !creature->getMap()) {
        return vstd::later([]() { return ZERO; });
    }
    auto deferredContext = capture_deferred_creature_context(creature);
    auto sourceMap = deferredContext.map.lock();
    auto target_object = sourceMap ? sourceMap->getObjectByName(target) : nullptr;
    if (!target_object) {
        return vstd::later([deferredContext]() { return deferredContext.fallback; });
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
        return find_shared_target_next_step(map, creature, target_object);
    });
}

std::shared_ptr<vstd::future<Coords, void>> CController::control(std::shared_ptr<CCreature> c) {
    if (!c) {
        return vstd::later([]() { return ZERO; });
    }
    auto deferredContext = capture_deferred_creature_context(c);
    return vstd::later([deferredContext]() {
        std::shared_ptr<CCreature> creature;
        std::shared_ptr<CMap> map;
        return resolve_deferred_creature_context(deferredContext, creature, map) ? creature->getCoords()
                                                                                 : deferredContext.fallback;
    });
}

void CController::onStepCommitted(std::shared_ptr<CCreature>, const Coords &) {}

void CController::interrupt(std::shared_ptr<CCreature>) {}

void CController::onTurnEnded(std::shared_ptr<CCreature>) {}

std::string CTargetController::getTarget() { return target; }

void CTargetController::setTarget(std::string target) { this->target = target; }

std::shared_ptr<vstd::future<Coords, void>> CRandomController::control(std::shared_ptr<CCreature> creature) {
    if (!creature) {
        return vstd::later([]() { return ZERO; });
    }
    auto deferredContext = capture_deferred_creature_context(creature);
    return vstd::later([deferredContext]() {
        std::shared_ptr<CCreature> creature;
        std::shared_ptr<CMap> map;
        if (!resolve_deferred_creature_context(deferredContext, creature, map)) {
            return deferredContext.fallback;
        }
        Coords target = creature->getCoords() + Coords(vstd::rand(-1, 1), vstd::rand(-1, 1), 0);
        return map->normalizeCoords(target);
    });
}

std::shared_ptr<vstd::future<Coords, void>> CNpcRandomController::control(std::shared_ptr<CCreature> creature) {
    auto self = this->ptr<CNpcRandomController>();
    if (!creature || !creature->getMap()) {
        return vstd::later([creature]() { return creature ? creature->getCoords() : ZERO; });
    }
    auto deferredContext = capture_deferred_creature_context(creature);
    return vstd::later([self, deferredContext]() -> Coords {
        std::shared_ptr<CCreature> creature;
        std::shared_ptr<CMap> map;
        if (!resolve_deferred_creature_context(deferredContext, creature, map)) {
            return deferredContext.fallback;
        }
        if (!self->path.empty() && self->currentStep < static_cast<int>(self->path.size())) {
            auto next = map->normalizeCoords(self->path[self->currentStep]);
            if (creature_can_follow_step(map, creature, next)) {
                return next;
            }
            self->path.clear();
            self->currentStep = 0;
        }

        if (self->path.empty() || self->currentStep >= static_cast<int>(self->path.size())) {
            for (int i = 0; i < 10; i++) {
                auto dx = vstd::rand(-5, 5);
                auto dy = vstd::rand(-5, 5);
                auto candidate = map->normalizeCoords(creature->getCoords() + Coords(dx, dy, 0));
                if (map->canStep(candidate)) {
                    self->path = CPathFinder::findPath(
                        creature->getCoords(), candidate, [map](const Coords &c) { return map->canStep(c); },
                        [](auto) -> std::optional<Coords> { return std::nullopt; },
                        [map](const Coords &coords) { return map->getNavigationNeighbors(coords); },
                        [map](const Coords &from, const Coords &to) { return map->getDistance(from, to); },
                        [map](const Coords &from, const Coords &to) { return movement_step_cost(map, from, to); });
                    self->currentStep = 0;
                    break;
                }
            }
        }

        if (!self->path.empty() && self->currentStep < static_cast<int>(self->path.size())) {
            auto next = map->normalizeCoords(self->path[self->currentStep]);
            if (creature_can_follow_step(map, creature, next)) {
                return next;
            }
            self->path.clear();
            self->currentStep = 0;
        }

        return creature->getCoords();
    });
}

void CNpcRandomController::onStepCommitted(std::shared_ptr<CCreature>, const Coords &) { currentStep++; }

void CNpcRandomController::interrupt(std::shared_ptr<CCreature>) {
    path.clear();
    currentStep = 0;
}

std::string CGroundController::getTileType() { return _tileType; }

void CGroundController::setTileType(std::string type) { _tileType = type; }

std::shared_ptr<vstd::future<Coords, void>> CGroundController::control(std::shared_ptr<CCreature> creature) {
    auto self = this->ptr<CGroundController>();
    if (!creature || !creature->getMap()) {
        return vstd::later([creature]() { return creature ? creature->getCoords() : ZERO; });
    }
    auto deferredContext = capture_deferred_creature_context(creature);
    return vstd::later([self, deferredContext]() -> Coords {
        std::shared_ptr<CCreature> creature;
        std::shared_ptr<CMap> map;
        if (!resolve_deferred_creature_context(deferredContext, creature, map)) {
            return deferredContext.fallback;
        }
        std::vector<Coords> possible;
        for (auto c : map->getAdjacentCoords(creature->getCoords(), true)) {
            std::string type = map->getTile(c)->getTileType();
            if (type == self->getTileType() && map->canStep(c)) {
                possible.push_back(c);
            }
        }
        if (!possible.empty()) {
            return *vstd::random_element(possible);
        }
        return creature->getCoords();
    });
}

CRangeController::CRangeController() {}

std::shared_ptr<vstd::future<Coords, void>> CRangeController::control(std::shared_ptr<CCreature> creature) {
    auto self = this->ptr<CRangeController>();
    if (!creature || !creature->getMap()) {
        return vstd::later([creature]() { return creature ? creature->getCoords() : ZERO; });
    }
    auto deferredContext = capture_deferred_creature_context(creature);
    return vstd::later([self, deferredContext]() -> Coords {
        std::shared_ptr<CCreature> creature;
        std::shared_ptr<CMap> map;
        if (!resolve_deferred_creature_context(deferredContext, creature, map)) {
            return deferredContext.fallback;
        }
        std::vector<Coords> possible;
        std::shared_ptr<CMapObject> targetObject = map->getObjectByName(self->getTarget());
        for (auto c : map->getAdjacentCoords(creature->getCoords(), true)) {
            if ((!targetObject || map->getDistance(targetObject->getCoords(), c) < self->distance) && map->canStep(c)) {
                possible.push_back(c);
            }
        }
        if (!possible.empty()) {
            return *vstd::random_element(possible);
        }
        return creature->getCoords();
    });
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
int strongest_heal_estimate(const std::shared_ptr<CCreature> &me) {
    int bestPower = 0;
    for (const auto &item : me->getItems()) {
        if (item && item->hasTag(CTag::Heal)) {
            bestPower = std::max(bestPower, item->getPower());
        }
    }
    const int uncapped = bestPower * me->getHpMax() / 5;
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
    return strongest_heal_estimate(me) > incoming;
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
    if (auto action = selectInteraction(me)) {
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

// TODO: use buffs
std::shared_ptr<CInteraction> CMonsterFightController::selectInteraction(std::shared_ptr<CCreature> cr) {
    std::function<bool(std::shared_ptr<CInteraction>)> pFunction = [](const std::shared_ptr<CInteraction> &it) {
        return !it->hasTag(CTag::Buff);
    };
    std::function<bool(std::shared_ptr<CInteraction>)> pFunction2 = [cr](const std::shared_ptr<CInteraction> &it) {
        return it->getManaCost() <= cr->getMana();
    };
    std::function<bool(std::shared_ptr<CInteraction>)> pFunction3 = [](const std::shared_ptr<CInteraction> &it) {
        return !it->getEffect() || (it->getEffect() && !it->getEffect()->hasTag(CTag::Buff));
    };
    auto pred = [](const std::shared_ptr<CInteraction> &a, const std::shared_ptr<CInteraction> &b) {
        return a->getManaCost() < b->getManaCost();
    };
    std::set<std::shared_ptr<CInteraction>> interactions = cr->getInteractions();
    auto rng =
        interactions | std::views::filter(pFunction) | std::views::filter(pFunction2) | std::views::filter(pFunction3);
    auto max = std::ranges::max_element(rng, pred);
    if (max != std::ranges::end(rng)) {
        return *max;
    }
    return {};
}

std::shared_ptr<vstd::future<Coords, void>> CPlayerController::control(std::shared_ptr<CCreature> c) {
    auto player = vstd::cast<CPlayer>(c);
    if (!player) {
        return vstd::now([]() { return ZERO; });
    }
    return vstd::now([this, player]() {
        if (!canContinue(player)) {
            return player->getCoords();
        }
        return path.at(currentStep);
    });
}

void CPlayerController::setTarget(std::shared_ptr<CPlayer> player, Coords _target) {
    if (!player || !player->getMap()) {
        clearPath();
        return;
    }
    auto map = player->getMap();
    auto normalized = map->normalizeCoords(_target);
    // Reject targets outside the configured map extents before invoking the pathfinder so that
    // arbitrary (potentially adversarial) coordinates cannot trigger a search over unbounded space.
    // Note: passability of the goal tile is intentionally NOT checked here. A* exempts the goal from
    // the canStep test, so legitimately targeting a momentarily non-steppable in-bounds tile (e.g.
    // one occupied by a transition object or creature) must still compute a path. The pathfinder's
    // envelope / node / path-length budgets bound the search even for adversarial in-bounds goals.
    if (!map->isWithinBounds(normalized)) {
        clearPath();
        return;
    }
    target = std::make_shared<Coords>(normalized);
    path.clear();
    currentStep = 0;
    auto _path = calculatePath(player);
    for (int i = 0; i < static_cast<int>(_path.size()); i++) {
        path[i] = _path[i];
    }
}

void CPlayerController::onStepCommitted(std::shared_ptr<CCreature>, const Coords &coords) {
    auto it = path.find(currentStep);
    if (it != path.end() && it->second == coords) {
        currentStep++;
    } else {
        clearPath();
    }
}

void CPlayerController::interrupt(std::shared_ptr<CCreature>) { clearPath(); }

void CPlayerController::onTurnEnded(std::shared_ptr<CCreature>) {}

// TODO: add stopping when obstacle found
std::pair<bool, Coords::Direction> CPlayerController::isOnPath(std::shared_ptr<CPlayer> player, Coords coords) {
    if (!isCompleted(player)) {
        for (auto it : path | std::views::filter([this](auto it) { return it.first >= currentStep - 1; })) {
            if (it.second == coords) {
                auto prev = it.first > 0 ? path[it.first - 1] : player->getCoords();
                auto dir = player->getMap()->getShortestDelta(prev, coords);
                return std::make_pair(true, CUtil::getDirection(dir));
            }
        }
    }
    return std::make_pair(false, Coords::Direction::ZERO);
}

bool CPlayerController::isCompleted(std::shared_ptr<CPlayer> player) { return !hasPendingPath(player); }

void CPlayerController::clearPath() {
    target.reset();
    path.clear();
    currentStep = 0;
}

bool CPlayerController::hasPendingPath(std::shared_ptr<CPlayer> player) {
    if (!target || currentStep < 0 || !player || !player->getMap()) {
        return false;
    }
    auto map = player->getMap();
    auto normalized_target = map->normalizeCoords(*target);
    if (player->getCoords() == normalized_target || !map->canStep(normalized_target)) {
        return false;
    }
    auto it = path.find(currentStep);
    if (it == path.end()) {
        return false;
    }
    auto next = map->normalizeCoords(it->second);
    return next != player->getCoords() && map->canStep(next) &&
           contains_navigation_neighbor(map, player->getCoords(), next);
}

bool CPlayerController::canContinue(std::shared_ptr<CPlayer> player) { return hasPendingPath(player); }

std::vector<Coords> CPlayerController::calculatePath(std::shared_ptr<CPlayer> player) {
    return CPathFinder::findPath(
        player->getCoords(), *target, [player](Coords coords) { return player->getMap()->canStep(coords); },
        [](auto) -> std::optional<Coords> { return std::nullopt; },
        [player](const Coords &coords) { return player->getMap()->getNavigationNeighbors(coords); },
        [player](const Coords &from, const Coords &to) { return player->getMap()->getDistance(from, to); },
        [player](const Coords &from, const Coords &to) { return movement_step_cost(player->getMap(), from, to); });
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
