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

#include "core/CGame.h"
#include "core/CMap.h"
#include "gui/panel/CGameFightPanel.h"
#include "object/CMapObject.h"
#include "object/CPlayer.h"

namespace {
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
};

std::mutex targetFlowMutex;
std::vector<std::shared_ptr<TargetFlowField>> targetFlowCache;

bool creature_can_follow_step(const std::shared_ptr<CCreature> &creature, const Coords &step) {
    if (!creature || !creature->getMap()) {
        return false;
    }
    auto map = creature->getMap();
    auto current = map->normalizeCoords(creature->getCoords());
    auto target = map->normalizeCoords(step);
    return target != current && map->canStep(target);
}

std::shared_ptr<TargetFlowField> build_target_flow_field(const std::shared_ptr<CMap> &map, const Coords &goal,
                                                         std::uint64_t revision) {
    auto field = std::make_shared<TargetFlowField>();
    field->map = map;
    field->revision = revision;
    field->goal = goal;

    if (!map->canStep(goal)) {
        return field;
    }

    std::unordered_map<Coords, int> costs;
    std::priority_queue<FlowQueueNode, std::vector<FlowQueueNode>, FlowQueueCompare> frontier;
    costs[goal] = 0;
    frontier.push({0, goal});

    while (!frontier.empty()) {
        auto current = frontier.top();
        frontier.pop();

        auto best = costs.find(current.coords);
        if (best == costs.end() || best->second != current.cost) {
            continue;
        }

        for (auto previous : map->getAdjacentCoords(current.coords)) {
            if (previous != goal && !map->canStep(previous)) {
                continue;
            }

            const int nextCost = current.cost + 1;
            auto previousCost = costs.find(previous);
            if (previousCost == costs.end() || nextCost < previousCost->second) {
                costs[previous] = nextCost;
                field->nextSteps[previous] = current.coords;
                frontier.push({nextCost, previous});
            }
        }
    }

    return field;
}

std::shared_ptr<TargetFlowField> get_target_flow_field(const std::shared_ptr<CMap> &map, const Coords &goal) {
    constexpr std::size_t maxCachedFlowFields = 32;
    const auto revision = map->getNavigationRevision();
    std::lock_guard<std::mutex> lock(targetFlowMutex);

    targetFlowCache.erase(std::remove_if(targetFlowCache.begin(), targetFlowCache.end(),
                                         [](const auto &field) { return !field || field->map.expired(); }),
                          targetFlowCache.end());

    auto cached = std::find_if(targetFlowCache.begin(), targetFlowCache.end(), [&](const auto &field) {
        return field->map.lock() == map && field->revision == revision && field->goal == goal;
    });
    if (cached != targetFlowCache.end()) {
        return *cached;
    }

    auto field = build_target_flow_field(map, goal, revision);
    targetFlowCache.push_back(field);
    while (targetFlowCache.size() > maxCachedFlowFields) {
        targetFlowCache.erase(targetFlowCache.begin());
    }
    return field;
}

Coords find_shared_target_next_step(const std::shared_ptr<CCreature> &creature,
                                    const std::shared_ptr<CMapObject> &targetObject) {
    if (!creature || !targetObject || !creature->getMap()) {
        return creature ? creature->getCoords() : ZERO;
    }

    auto map = creature->getMap();
    auto start = map->normalizeCoords(creature->getCoords());
    auto goal = map->normalizeCoords(targetObject->getCoords());
    if (start == goal || !map->canStep(goal)) {
        return start;
    }

    auto flow = get_target_flow_field(map, goal);
    auto next = flow->nextSteps.find(start);
    if (next == flow->nextSteps.end()) {
        return start;
    }
    auto step = map->normalizeCoords(next->second);
    if (!creature_can_follow_step(creature, step)) {
        return start;
    }
    return step;
}
} // namespace

CTargetController::CTargetController() {}

std::shared_ptr<vstd::future<Coords, void>> CTargetController::control(std::shared_ptr<CCreature> creature) {
    auto target_object = creature->getMap()->getObjectByName(target);
    if (!target_object) {
        return vstd::later([creature]() { return creature->getCoords(); });
    }
    return vstd::async([creature, target_object]() { return find_shared_target_next_step(creature, target_object); });
}

std::shared_ptr<vstd::future<Coords, void>> CController::control(std::shared_ptr<CCreature> c) {
    return vstd::later([c]() { return c->getCoords(); });
}

void CController::onStepCommitted(std::shared_ptr<CCreature>, const Coords &) {}

void CController::interrupt(std::shared_ptr<CCreature>) {}

void CController::onTurnEnded(std::shared_ptr<CCreature>) {}

std::string CTargetController::getTarget() { return target; }

void CTargetController::setTarget(std::string target) { this->target = target; }

std::shared_ptr<vstd::future<Coords, void>> CRandomController::control(std::shared_ptr<CCreature> creature) {
    return vstd::later([creature]() {
        Coords target = creature->getCoords() + Coords(vstd::rand(-1, 1), vstd::rand(-1, 1), 0);
        return creature->getMap() ? creature->getMap()->normalizeCoords(target) : target;
    });
}

std::shared_ptr<vstd::future<Coords, void>> CNpcRandomController::control(std::shared_ptr<CCreature> creature) {
    auto self = this->ptr<CNpcRandomController>();
    return vstd::later([self, creature]() -> Coords {
        if (!self->path.empty() && self->currentStep < static_cast<int>(self->path.size())) {
            auto next = creature->getMap()->normalizeCoords(self->path[self->currentStep]);
            if (creature_can_follow_step(creature, next)) {
                return next;
            }
            self->path.clear();
            self->currentStep = 0;
        }

        if (self->path.empty() || self->currentStep >= static_cast<int>(self->path.size())) {
            for (int i = 0; i < 10; i++) {
                auto dx = vstd::rand(-5, 5);
                auto dy = vstd::rand(-5, 5);
                auto candidate = creature->getMap()->normalizeCoords(creature->getCoords() + Coords(dx, dy, 0));
                if (creature->getMap()->canStep(candidate)) {
                    self->path = CPathFinder::findPath(
                        creature->getCoords(), candidate,
                        [creature](const Coords &c) { return creature->getMap()->canStep(c); },
                        [](auto) -> std::optional<Coords> { return std::nullopt; },
                        [creature](const Coords &coords) { return creature->getMap()->getAdjacentCoords(coords); },
                        [creature](const Coords &from, const Coords &to) {
                            return creature->getMap()->getDistance(from, to);
                        });
                    self->currentStep = 0;
                    break;
                }
            }
        }

        if (!self->path.empty() && self->currentStep < static_cast<int>(self->path.size())) {
            auto next = creature->getMap()->normalizeCoords(self->path[self->currentStep]);
            if (creature_can_follow_step(creature, next)) {
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
    return vstd::later([self, creature]() -> Coords {
        std::vector<Coords> possible;
        for (auto c : creature->getMap()->getAdjacentCoords(creature->getCoords(), true)) {
            std::string type = creature->getMap()->getTile(c)->getTileType();
            if (type == self->getTileType() && creature->getMap()->canStep(c)) {
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
    return vstd::later([self, creature]() -> Coords {
        std::vector<Coords> possible;
        std::shared_ptr<CMapObject> targetObject = creature->getMap()->getObjectByName(self->getTarget());
        for (auto c : creature->getMap()->getAdjacentCoords(creature->getCoords(), true)) {
            if ((!targetObject || creature->getMap()->getDistance(targetObject->getCoords(), c) < self->distance) &&
                creature->getMap()->canStep(c)) {
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

bool CMonsterFightController::control(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) {
    if (me->getHpRatio() < 75) {
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
    return vstd::now([this, player]() {
        if (!canContinue(player)) {
            return player->getCoords();
        }
        return path.at(currentStep);
    });
}

void CPlayerController::setTarget(std::shared_ptr<CPlayer> player, Coords _target) {
    target = std::make_shared<Coords>(player->getMap()->normalizeCoords(_target));
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
    return next != player->getCoords() && map->canStep(next);
}

bool CPlayerController::canContinue(std::shared_ptr<CPlayer> player) { return hasPendingPath(player); }

std::vector<Coords> CPlayerController::calculatePath(std::shared_ptr<CPlayer> player) {
    return CPathFinder::findPath(
        player->getCoords(), *target, [player](Coords coords) { return player->getMap()->canStep(coords); },
        [player](auto coords) -> std::optional<Coords> {
            for (auto ob : player->getMap()->getObjectsAtCoords(coords)) {
                if (ob->getBoolProperty("waypoint")) {
                    return Coords(ob->getNumericProperty("x"), ob->getNumericProperty("y"),
                                  ob->getNumericProperty("z"));
                }
            }
            return std::nullopt;
        },
        [player](const Coords &coords) { return player->getMap()->getAdjacentCoords(coords); },
        [player](const Coords &from, const Coords &to) { return player->getMap()->getDistance(from, to); });
}

bool CFightController::control(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) {
    vstd::logger::warning("Empty fight controller used!");
    return true;
}

void CFightController::start(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) {}

void CFightController::end(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) {}

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
    vstd::if_not_null(me->getMap()->getGame()->getGui(), [&](auto gui) {
        fightPanel = me->getGame()->createObject<CGameFightPanel>("fightPanel");
        fightPanel->setEnemies({opponent});
        gui->pushChild(fightPanel);
    });
}

bool CPlayerFightController::control(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) {
    bool used = false;
    vstd::if_not_null(me->getMap()->getGame()->getGui(), [&](auto gui) {
        // TODO: what about mana cost?
        auto target = fightPanel && fightPanel->getEnemy() ? fightPanel->getEnemy() : opponent;
        if (auto action = fightPanel->selectInteraction()) {
            me->useAction(action, target);
            used = true;
        }
    });
    return used;
}

void CPlayerFightController::end(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) {
    vstd::if_not_null(me->getMap()->getGame()->getGui(), [&](auto gui) {
        if (fightPanel) {
            fightPanel->close();
            fightPanel = nullptr;
        }
    });
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
