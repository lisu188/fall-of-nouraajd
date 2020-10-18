/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

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
#include "core/CMap.h"
#include "core/CGame.h"
#include "core/CController.h"
#include "object/CTrigger.h"


std::map<int, std::pair<int, int> > CMap::getBounds() {
    return boundaries;
}

void CMap::removeObjectByName(std::string name) {
    this->removeObject(this->getObjectByName(name));
}

std::string CMap::addObjectByName(std::string name, Coords coords) {
    if (this->canStep(coords)) {
        std::shared_ptr<CMapObject> object = getGame()->createObject<CMapObject>(name);
        if (object) {
            addObject(object);
            object->moveTo(coords.x, coords.y, coords.z);
            return name;
        }
    }
    return "";
}

void CMap::replaceTile(std::string name, Coords coords) {
    removeTile(coords.x, coords.y, coords.z);
    addTile(getGame()->createObject<CTile>(name), coords.x, coords.y, coords.z);
}

Coords CMap::getLocationByName(std::string name) {
    return this->getObjectByName(name)->getCoords();
}

std::shared_ptr<CPlayer> CMap::getPlayer() {
    //TODO: think of better solution after save
    if (!player) {
        for (auto object:getObjects()) {
            if (auto pl = vstd::cast<CPlayer>(object)) {
                this->player = pl;
                break;
            }
        }
    }
    return player;
}

void CMap::setPlayer(std::shared_ptr<CPlayer> player) {
    addObject(player);
    player->moveTo(entryx, entryy, entryz);
    this->player = player;
}


std::shared_ptr<CEventHandler> CMap::getEventHandler() {
    return eventHandler.get([this]() {
        return std::make_shared<CEventHandler>();
    });
}

void CMap::moveTile(std::shared_ptr<CTile> tile, int x, int y, int z) {
    Coords coords = tile->getCoords();
    auto it = tiles.find(coords);
    if (it != tiles.end()) {
        tiles.erase(it);
    }
    tiles.insert(std::make_pair(Coords(x, y, z), tile));
    signal("tileChanged", Coords(x, y, z));
}

bool CMap::addTile(std::shared_ptr<CTile> tile, int x, int y, int z) {
    if (this->contains(x, y, z)) {
        return false;
    }
    tiles.insert(std::make_pair(Coords(x, y, z), tile));
    tile->moveTo(x, y, z);
//    signal("tileChanged", Coords(x, y, z)); //moveTo already sends signal
    return true;
}

void CMap::removeTile(int x, int y, int z) {
    this->tiles.erase(this->tiles.find(Coords(x, y, z)));
    signal("tileChanged", Coords(x, y, z));
}

std::shared_ptr<CTile> CMap::getTile(int x, int y, int z) {
    Coords coords(x, y, z);
    std::shared_ptr<CTile> tile;
    auto it = this->tiles.find(coords);
    if (it == this->tiles.end()) {
        if (vstd::ctn(boundaries, z) && (x < 0 || y < 0 || x > boundaries[z].first || y > boundaries[z].second)) {
            tile = getGame()->createObject<CTile>("MountainTile");
        } else {
            tile = getGame()->createObject<CTile>(
                    vstd::ctn(boundaries, z) &&
                    !defaultTiles[z].empty() ? defaultTiles[z] : "GrassTile");
        }
        if (tile) {
            this->addTile(tile, x, y, z);
        }
    } else {
        tile = (*it).second;
    }
    return tile;
}

std::shared_ptr<CTile> CMap::getTile(Coords coords) {
    return this->getTile(coords.x, coords.y, coords.z);
}

bool CMap::canStep(int x, int y, int z) {
    Coords coords(x, y, z);
    auto it = this->tiles.find(coords);
    if (it != this->tiles.end()) {
        return (*it).second->canStep();
    }
    std::pair<int, int> bound = boundaries[z];
    return !(x < 0 || y < 0 || x > bound.first || y > bound.second);
}

bool CMap::canStep(Coords coords) {
    return canStep(coords.x, coords.y, coords.z);
}

bool CMap::contains(int x, int y, int z) {
    Coords coords(x, y, z);
    auto it = tiles.find(coords);
    return it != tiles.end();
}

void CMap::addObject(std::shared_ptr<CMapObject> mapObject) {
    vstd::fail_if(vstd::ctn(mapObjects, mapObject->getName()),
                  "Map object already exists: " + mapObject->getName());
    std::shared_ptr<CCreature> creature = vstd::cast<CCreature>(mapObject);
    if (creature.get()) {
        if (creature->getLevel() == 0) {
            creature->levelUp();
            creature->heal(0);
            creature->addMana(0);
        }
        creature->addExp(0);
    }
    mapObjects.insert(std::make_pair(mapObject->getName(), mapObject));
    getEventHandler()->gameEvent(mapObject, std::make_shared<CGameEvent>(CGameEvent::Type::onCreate));
    signal("objectChanged", mapObject->getCoords());
}

void CMap::removeObject(std::shared_ptr<CMapObject> mapObject) {
    mapObjects.erase(mapObjects.find(mapObject->getName()));
    getEventHandler()->gameEvent(mapObject, std::make_shared<CGameEvent>(CGameEvent::Type::onDestroy));
    signal("objectChanged", mapObject->getCoords());
}

int CMap::getEntryX() {
    return entryx;
}

int CMap::getEntryY() {
    return entryy;
}

int CMap::getEntryZ() {
    return entryz;
}

std::shared_ptr<CMapObject> CMap::getObjectByName(std::string name) {
    auto it = mapObjects.find(name);
    if (it != mapObjects.end()) {
        return (*it).second;
    }
    return std::shared_ptr<CMapObject>();
}

bool CMap::isMoving() {
    return moving;
}

//void CMap::applyEffects() {
//    auto pred = [](std::shared_ptr<CMapObject> object) {
//        return vstd::castable<CCreature>(object);
//    };
//    for (std::shared_ptr<CMapObject> object:mapObjects |
//                                            boost::adaptors::map_values |
//                                            boost::adaptors::filtered(pred)) {
//        vstd::cast<CCreature>(object)->applyEffects();
//    }
//}

void CMap::forObjects(std::function<void(std::shared_ptr<CMapObject>)> func,
                      std::function<bool(std::shared_ptr<CMapObject>)> predicate) {
    auto clone = mapObjects;
    for (std::shared_ptr<CMapObject> object : clone |
                                              boost::adaptors::map_values |
                                              boost::adaptors::filtered(predicate)) {
        func(object);
    }
}

void CMap::forTiles(std::function<void(std::shared_ptr<CTile>)> func,
                    std::function<bool(std::shared_ptr<CTile>)> predicate) {
    for (std::shared_ptr<CTile> tile:(tiles |
                                      boost::adaptors::map_values |
                                      boost::adaptors::filtered(predicate))) {
        func(tile);
    }
}


void CMap::removeObjects(std::function<bool(std::shared_ptr<CMapObject>)> func) {
    auto clone = mapObjects;
    for (std::shared_ptr<CMapObject> object : clone |
                                              boost::adaptors::map_values |
                                              boost::adaptors::filtered(func)) {
        removeObject(object);
    }
}

void CMap::move() {
    auto map = this->ptr<CMap>();

    if (map->moving) {
        vstd::logger::fatal("Invalid move request");
    }

    map->moving = true;

    vstd::logger::debug("Turn:", map->turn);

    //TODO: map->applyEffects();

    map->forObjects([map](std::shared_ptr<CMapObject> mapObject) {
        map->getEventHandler()->gameEvent(mapObject, std::make_shared<CGameEvent>(CGameEvent::Type::onTurn));
    });

    auto pred = [](std::shared_ptr<CMapObject> object) {
        return vstd::castable<Moveable>(object);
    };

    auto controller = [map](std::shared_ptr<CMapObject> object) {
        return vstd::cast<CCreature>(object)->getController()->control(vstd::cast<CCreature>(object));
    };

    auto end_callback = [map](std::set<void *>) {
        map->resolveFights();
        map->moving = false;
        map->turn++;
        map->signal("turnPassed");
    };

    //TODO: return future and replace
    vstd::join(map->mapObjects |
               boost::adaptors::map_values |
               boost::adaptors::filtered(pred) |
               boost::adaptors::transformed(controller))
            ->thenLater(end_callback);

    vstd::wait_until([map]() {
        return !map->moving;
    });
}

void CMap::resolveFights() {
    forObjects([this](std::shared_ptr<CMapObject> mapObject) {
        auto action = [this, mapObject](std::shared_ptr<CMapObject> visitor) {
            if (getObjectByName(mapObject->getName()) && getObjectByName(visitor->getName())) {
                CFightHandler::fight(vstd::cast<CCreature>(mapObject), vstd::cast<CCreature>(visitor));
            }
        };
        auto pred = [mapObject](std::shared_ptr<CMapObject> visitor) {
            return vstd::cast<CCreature>(mapObject) && vstd::cast<CCreature>(visitor)
                   && mapObject != visitor
                   && mapObject->getCoords() == visitor->getCoords()
                   && !mapObject->isAffiliatedWith(visitor);
        };
        forObjects(action, pred);
    });
}


CMap::CMap() {

}

int CMap::getTurn() {
    return turn;
}

void CMap::setTurn(int turn) {
    this->turn = turn;
}

void CMap::setTiles(std::set<std::shared_ptr<CTile>> objects) {
    for (auto ob : objects) {
        tiles[ob->getCoords()] = ob;
    }
}

std::set<std::shared_ptr<CTile>> CMap::getTiles() {
    return vstd::cast<std::set<std::shared_ptr<CTile>>>(tiles | boost::adaptors::map_values);
}

void CMap::setObjects(std::set<std::shared_ptr<CMapObject>> objects) {
    for (auto ob : objects) {
        mapObjects[ob->getName()] = ob;
    }
}

std::set<std::shared_ptr<CMapObject>> CMap::getObjects() {
    return vstd::cast<std::set<std::shared_ptr<CMapObject>>>(mapObjects | boost::adaptors::map_values);
}

void CMap::dumpPaths(std::string path) {
    CPathFinder::saveMap(getPlayer()->getCoords(), [this](auto coords) {
        return this->canStep(coords);
    }, path);
}

std::set<std::shared_ptr<CTrigger>> CMap::getTriggers() {
    return getEventHandler()->getTriggers();
}

void CMap::setTriggers(std::set<std::shared_ptr<CTrigger>> triggers) {
    for (auto trigger:triggers) {
        getEventHandler()->registerTrigger(trigger);
    }
}

void CMap::setMapName(std::string mapName) {
    this->mapName = mapName;
}

std::string CMap::getMapName() {
    return mapName;
}

void CMap::objectMoved(std::shared_ptr<CMapObject> object, Coords _old, Coords _new) {
    //TODO: implement own erase if
    auto range = mapObjectsCache.equal_range(_old);

    for (auto it = range.first; it != range.second; ++it) {
        if (it->second == object->getName()) {
            mapObjectsCache.erase(it);
            break;
        }
    }

    mapObjectsCache.insert(std::make_pair(_new, object->getName()));

    //TODO: check if it`s correct
    signal("objectChanged", _old);
    signal("objectChanged", _new);
}

std::set<std::shared_ptr<CMapObject>> CMap::getObjectsAtCoords(Coords coords) {
    std::set<std::shared_ptr<CMapObject>> ret;
    auto range = mapObjectsCache.equal_range(
            coords);
    for (auto it = range.first; it != range.second; it++) {
        if (auto ob = getObjectByName(it->second)) {
            ret.insert(ob);
        }
    }
    return ret;
}

