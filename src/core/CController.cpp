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

std::shared_ptr<vstd::future<void, Coords> > CController::control(std::shared_ptr<CCreature> c) {
    return vstd::async([](Coords) {});
}

CTargetController::CTargetController() {

}

std::shared_ptr<CMapObject> CTargetController::get_target() {
    return target;
}

void CTargetController::set_target(std::shared_ptr<CMapObject> target) {
    this->target = target;
}

std::shared_ptr<vstd::future<void, Coords> > CRandomController::control(std::shared_ptr<CCreature> creature) {
    return vstd::later([]() {
        return Coords(vstd::rand(-1, 1), vstd::rand(-1, 1), 0);
    })->thenLater([=](Coords coords) {
        creature->moveTo(coords);
    });
}

std::string CGroundController::getTileType() { return _tileType; }

void CGroundController::setTileType(std::string type) { _tileType = type; }

std::shared_ptr<vstd::future<void, Coords> > CGroundController::control(std::shared_ptr<CCreature> creature) {
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


std::shared_ptr<vstd::future<void, Coords> > CRangeController::control(std::shared_ptr<CCreature> creature) {
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

bool CFightController::control(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) {
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


std::shared_ptr<CItem> CFightController::getLeastPowerfulItemWithTag(std::shared_ptr<CCreature> cr, std::string tag) {
    auto cmp = [](std::shared_ptr<CItem> a, std::shared_ptr<CItem> b) {
        return a->getPower() < b->getPower();
    };
    std::function<bool(std::shared_ptr<CItem>)> pred = [tag](std::shared_ptr<CItem> it) {
        return it->hasTag(tag);
    };
    auto rng = cr->getItems() | boost::adaptors::filtered(pred);
    auto max = boost::min_element(rng, cmp);
    if (max != boost::end(rng)) {
        return *max;
    }
    return std::shared_ptr<CItem>();
}

std::shared_ptr<CInteraction> CFightController::selectInteraction(std::shared_ptr<CCreature> cr) {
    std::function<bool(std::shared_ptr<CInteraction>)> pFunction = [](std::shared_ptr<CInteraction> it) {
        return !it->hasTag("buff");
    };
    std::function<bool(std::shared_ptr<CInteraction>)> pFunction2 = [cr](std::shared_ptr<CInteraction> it) {
        return it->getManaCost() <= cr->getMana();
    };
    std::function<bool(std::shared_ptr<CInteraction>)> pFunction3 = [](std::shared_ptr<CInteraction> it) {
        return !it->getEffect() || (it->getEffect() && !it->getEffect()->hasTag("buff"));
    };
    auto pred = [](std::shared_ptr<CInteraction> a, std::shared_ptr<CInteraction> b) {
        return a->getManaCost() < b->getManaCost();
    };
    auto rng = cr->getInteractions() | boost::adaptors::filtered(pFunction) |
               boost::adaptors::filtered(pFunction2) | boost::adaptors::filtered(pFunction3);
    auto max = boost::max_element(
            rng, pred);
    if (max != boost::end(rng)) {
        return *max;
    }
    return std::shared_ptr<CInteraction>();
}

CPlayerController::CPlayerController() {
    this->next = std::make_shared<Coords>(0, 0, 0);
}


CPlayerController::CPlayerController(Coords next) {
    this->next = std::make_shared<Coords>(next);
}

std::shared_ptr<vstd::future<void, Coords> > CPlayerController::control(std::shared_ptr<CCreature> c) {
    return vstd::later([=](Coords coords) {
        c->move(*next);
    });
}
