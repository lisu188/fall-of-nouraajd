#include "object/CMapObject.h"
#include "core/CController.h"

CTargetController::CTargetController(std::shared_ptr<CMapObject> target) : target(target) {

}

std::shared_ptr<vstd::future<void, Coords>> CTargetController::control(std::shared_ptr<CCreature> creature) {
    return CPathFinder::findNextStep(creature->getCoords(), target->getCoords(), [creature](const Coords &coords) {
        return creature->getMap()->canStep(coords);
    })->thenLater([creature](Coords coords) {
        creature->moveTo(coords);
    });
}

std::shared_ptr<vstd::future<void, Coords> >  CController::control(std::shared_ptr<CCreature> c) {
    return vstd::async([](Coords) { });
}

CTargetController::CTargetController() {

}

std::shared_ptr<CMapObject> CTargetController::get_target() {
    return target;
}

void CTargetController::set_target(std::shared_ptr<CMapObject> target) {
    this->target = target;
}

std::shared_ptr<vstd::future<void, Coords> >  CRandomController::control(std::shared_ptr<CCreature> creature) {
    return vstd::later([]() {
        return Coords(vstd::rand(-1, 1), vstd::rand(-1, 1), 0);
    })->thenLater([=](Coords coords) {
        creature->moveTo(coords);
    });
}

std::string CGroundController::getTileType() { return _tileType; }

void CGroundController::setTileType(std::string type) { _tileType = type; }

std::shared_ptr<vstd::future<void, Coords> >  CGroundController::control(std::shared_ptr<CCreature> creature) {
    return vstd::later([=]() -> Coords {
        std::vector<Coords> possible;
        for (auto c:NEAR_COORDS_WITH(creature->getCoords())) {
            std::string type = creature->getMap()->getTile(c)->getTileType();
            if (type == this->getTileType() && creature->getMap()->canStep(c)) {
                possible.push_back(c);
            }
        }
        if (possible.size() > 0) {
            return possible[vstd::rand(0, possible.size())];
        }
        return creature->getCoords();
    })->thenLater([=](Coords coords) {
        creature->moveTo(coords);
    });
}

CRangeController::CRangeController() {

}


std::shared_ptr<vstd::future<void, Coords> >  CRangeController::control(std::shared_ptr<CCreature> creature) {
    return vstd::later([=]() -> Coords {
        std::vector<Coords> possible;
        for (auto c:NEAR_COORDS_WITH(creature->getCoords())) {
            if (creature->getMap()->getObjectByName(getTarget())->getCoords().getDist(c) < this->distance
                && creature->getMap()->canStep(c)) {
                possible.push_back(c);
            }
        }
        if (possible.size() > 0) {
            return possible[vstd::rand(0, possible.size())];
        }
        return creature->getCoords();
    })->thenLater([=](Coords coords) {
        creature->moveTo(coords);
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