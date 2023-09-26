/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2023  Andrzej Lis

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
#include "object/CMapObject.h"
#include "core/CController.h"
#include "gui/panel/CGameFightPanel.h"
#include "core/CGame.h"
#include "core/CMap.h"
#include "object/CPlayer.h"

CTargetController::CTargetController() {

}

std::shared_ptr<vstd::future<Coords, void>>
CTargetController::control(std::shared_ptr<CCreature>
                           creature) {
    return
            CPathFinder::findNextStep(creature->getCoords(),
                                      creature->getMap()->getObjectByName(target)->getCoords(), [creature](
                            const Coords &coords) {
                        return creature->getMap()->canStep(coords);
                    }, [](auto it) { return std::make_pair(false, ZERO); });
}

std::shared_ptr<vstd::future<Coords, void>>
CController::control(std::shared_ptr<CCreature>
                     c) {
    return vstd::later([c]() {
        return c->

                getCoords();

    });
}


std::string CTargetController::getTarget() {
    return target;
}

void CTargetController::setTarget(std::string target) {
    this->target = target;
}

std::shared_ptr<vstd::future<Coords, void>>
CRandomController::control(std::shared_ptr<CCreature>
                           creature) {
    return vstd::later([creature]() {
        return creature->

                getCoords()

               +
               Coords(vstd::rand(-1, 1), vstd::rand(-1, 1),
                      0);
    });
}

std::string CGroundController::getTileType() { return _tileType; }

void CGroundController::setTileType(std::string type) { _tileType = type; }

std::shared_ptr<vstd::future<Coords, void>>
CGroundController::control(std::shared_ptr<CCreature>
                           creature) {
    auto self = this->ptr<CGroundController>();
    return vstd::later([self, creature]() -> Coords {
        std::vector<Coords> possible;
        for (
            auto c
                :
                near_coords_with(creature
                                         ->

                                                 getCoords()

                )) {
            std::string type = creature->getMap()->getTile(c)->getTileType();
            if (type == self->

                    getTileType() &&

                creature->getMap()->
                        canStep(c)
                    ) {
                possible.
                        push_back(c);
            }
        }
        if (!possible.

                empty()

                ) {
            return
                    vstd::random_element(possible);
        }
        return creature->

                getCoords();

    });
}

CRangeController::CRangeController() {

}

std::shared_ptr<vstd::future<Coords, void>>
CRangeController::control(std::shared_ptr<CCreature>
                          creature) {
    auto self = this->ptr<CRangeController>();
    return vstd::later([self, creature]() -> Coords {
        std::vector<Coords> possible;
        std::shared_ptr<CMapObject> targetObject = creature->getMap()->getObjectByName(self->getTarget());
        for (
            auto c
                :
                near_coords_with(creature
                                         ->

                                                 getCoords()

                )) {
            if ((!targetObject || targetObject->

                            getCoords()

                                          .
                                                  getDist(c)
                                  < self->distance)
                && creature->getMap()->
                    canStep(c)
                    ) {
                possible.
                        push_back(c);
            }
        }
        if (!possible.

                empty()

                ) {
            return
                    vstd::random_element(possible);
        }
        return creature->

                getCoords();

    });
}

std::string CRangeController::getTarget() {
    return target;
}

void CRangeController::setTarget(std::string target) {
    this->target = target;
}

void CRangeController::setDistance(int distance) { this->distance = distance; }

int CRangeController::getDistance() { return distance; }

bool CMonsterFightController::control(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) {
    if (me->getHpRatio() < 75) {
        auto object = getLeastPowerfulItemWithTag(me, "heal");
        if (object) {
            me->useItem(object);
            return control(me, opponent);
        }
    }
    if (me->getManaRatio() < 75) {
        auto object = getLeastPowerfulItemWithTag(me, "mana");
        if (object) {
            me->useItem(object);
            return control(me, opponent);
        }
    }
    if (auto action = selectInteraction(me)) {
        me->useAction(action, opponent);
        return true;
    }
    return false;
}


std::shared_ptr<CItem>
CMonsterFightController::getLeastPowerfulItemWithTag(std::shared_ptr<CCreature> cr, std::string tag) {
    auto cmp = [](const std::shared_ptr<CItem> &a, const std::shared_ptr<CItem> &b) {
        return a->getPower() < b->getPower();
    };
    std::function<bool(std::shared_ptr<CItem>)> pred = [tag](const std::shared_ptr<CItem> &it) {
        return it->hasTag(tag);
    };
    std::set<std::shared_ptr<CItem>> items = cr->getItems();
    auto rng = items | boost::adaptors::filtered(pred);
    auto max = boost::min_element(rng, cmp);
    if (max != boost::end(rng)) {
        return *max;
    }
    return {};
}

//TODO: use buffs
std::shared_ptr<CInteraction> CMonsterFightController::selectInteraction(std::shared_ptr<CCreature> cr) {
    std::function<bool(std::shared_ptr<CInteraction>)> pFunction = [](const std::shared_ptr<CInteraction> &it) {
        return !it->hasTag("buff");
    };
    std::function<bool(std::shared_ptr<CInteraction>)> pFunction2 = [cr](const std::shared_ptr<CInteraction> &it) {
        return it->getManaCost() <= cr->getMana();
    };
    std::function<bool(std::shared_ptr<CInteraction>)> pFunction3 = [](const std::shared_ptr<CInteraction> &it) {
        return !it->getEffect() || (it->getEffect() && !it->getEffect()->hasTag("buff"));
    };
    auto pred = [](const std::shared_ptr<CInteraction> &a, const std::shared_ptr<CInteraction> &b) {
        return a->getManaCost() < b->getManaCost();
    };
    std::set<std::shared_ptr<CInteraction>> interactions = cr->getInteractions();
    auto rng = interactions | boost::adaptors::filtered(pFunction) |
               boost::adaptors::filtered(pFunction2) | boost::adaptors::filtered(pFunction3);
    auto max = boost::max_element(
            rng, pred);
    if (max != boost::end(rng)) {
        return *max;
    }
    return {};
}

std::shared_ptr<vstd::future<Coords, void>>
CPlayerController::control(std::shared_ptr<CCreature>
                           c) {
    return vstd::now([&]() {
        return
                isCompleted(vstd::cast<CPlayer>(c)
                ) ? c->

                        getCoords() : path

                [currentStep++];
    });
}


void CPlayerController::setTarget(std::shared_ptr<CPlayer> player, Coords _target) {
    target = std::make_shared<Coords>(_target);
    path.clear();
    currentStep = 0;
    auto _path = calculatePath(player);
    for (int i = 0; i < _path.size(); i++) {
        path[i] = _path[i];
    }
}

//TODO: add stopping when obstacle found
std::pair<bool, Coords::Direction> CPlayerController::isOnPath(std::shared_ptr<CPlayer> player, Coords coords) {
    if (!isCompleted(player)) {
        for (auto it: path | boost::adaptors::filtered([this](auto it) {
            return it.first >= currentStep - 1;
        })) {
            if (it.second == coords) {
                auto prev = it.first > 0 ? path[it.first - 1] : coords;
                auto dir = coords - prev;
                return std::make_pair(true, CUtil::getDirection(dir));
            }
        }
    }
    return std::make_pair(false, Coords::Direction::ZERO);
}

std::vector<Coords> CPlayerController::calculatePath(std::shared_ptr<CPlayer> player) {
    return CPathFinder::findPath(player->getCoords(),
                                 *target,
                                 [player](Coords coords) {
                                     return player->getMap()->canStep(
                                             coords);
                                 }, [player](auto coords) {
                //TODO: make it more efficient. cache?
                for (auto ob: player->getMap()->getObjectsAtCoords(coords)) {
                    if (ob->getBoolProperty("waypoint")) {
                        return std::make_pair(true,
                                              Coords(ob->getNumericProperty("x"),
                                                     ob->getNumericProperty("y"),
                                                     ob->getNumericProperty("z")));
                    }
                }
                return std::make_pair(false, ZERO);
            });
}

bool CFightController::control(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) {
    vstd::logger::warning("Empty fight controller used!");
    return true;
}

void CFightController::start(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) {

}

void CFightController::end(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) {

}


void CPlayerFightController::start(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) {
    vstd::if_not_null(me->getMap()->getGame()->getGui(), [&](auto gui) {
        fightPanel = me->getGame()->createObject<CGameFightPanel>("fightPanel");
        fightPanel->setEnemy(opponent);
        gui->pushChild(fightPanel);
        return 0;
    });
}

bool CPlayerFightController::control(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) {
    bool used = false;
    vstd::if_not_null(me->getMap()->getGame()->getGui(), [&](auto gui) {
        //TODO: what about mana cost?
        me->useAction(fightPanel->selectInteraction(), opponent);
        used = true;
    });
    return used;
}

void CPlayerFightController::end(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) {
    vstd::if_not_null(me->getMap()->getGame()->getGui(), [&](auto gui) {
        fightPanel->close();
        fightPanel = nullptr;
    });
}

bool CPlayerController::isCompleted(std::shared_ptr<CPlayer> player) {
    return !target
           || currentStep >= path.size()
           || currentStep < 0
           || player->getCoords() == *target
           || !player->getMap()->canStep(*target);
}

