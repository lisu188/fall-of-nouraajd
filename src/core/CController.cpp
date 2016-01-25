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
        creature->move(coords);
    });
}

std::string CGroundController::get_ground_type() { return _ground_type; }

void CGroundController::set_ground_type(std::string type) { _ground_type = type; }

std::shared_ptr<vstd::future<void, Coords> >  CGroundController::control(std::shared_ptr<CCreature> creature) {
    return vstd::later([=]() {
        std::vector<Coords> possible;
        for (auto c:NEAR_COORDS(creature->getCoords())) {
            if (creature->getMap()->getTile(c)->getType() == this->get_ground_type()) {
                possible.push_back(c);
            }
        }
        return possible[vstd::rand(0, possible.size())];
    })->thenLater([=](Coords coords) {
        creature->move(coords);
    });
}

CRangeController::CRangeController() {

}

CRangeController::CRangeController(std::shared_ptr<CMapObject> target) {
    this->target = target;
}

std::shared_ptr<vstd::future<void, Coords> >  CRangeController::control(std::shared_ptr<CCreature> creature) {
    return vstd::later([=]() {
        std::vector<Coords> possible;
        for (auto c:NEAR_COORDS(creature->getCoords())) {
            if (creature->getCoords().getDist(c) < this->distance) {
                possible.push_back(c);
            }
        }
        return possible[vstd::rand(0, possible.size())];
    })->thenLater([=](Coords coords) {
        creature->move(coords);
    });
}

std::shared_ptr<CMapObject> CRangeController::get_target() {
    return target;
}

void CRangeController::set_target(std::shared_ptr<CMapObject> target) {
    this->target = target;
}

void CRangeController::set_distance(int distance) { this->distance = distance; }

int CRangeController::get_distance() { return distance; }