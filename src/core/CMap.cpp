#include "core/CMap.h"
#include "core/CGame.h"
#include "core/CController.h"
#include "object/CTrigger.h"

CMap::CMap(std::shared_ptr<CGame> game) : game(game) {

}

void CMap::ensureTile(int i, int j) {
    Coords coords(i, j, currentLevel);
    if (tiles.find(coords) == tiles.end()) {
        this->getTile(i, j, currentLevel);
    }
}

std::map<int, std::pair<int, int> > CMap::getBounds() {
    return boundaries;
}

int CMap::getCurrentXBound() {
    return boundaries[currentLevel].first;
}

int CMap::getCurrentYBound() {
    return boundaries[currentLevel].second;
}

void CMap::removeObjectByName(std::string name) {
    this->removeObject(this->getObjectByName(name));
}

std::string CMap::addObjectByName(std::string name, Coords coords) {
    if (this->canStep(coords)) {
        std::shared_ptr<CMapObject> object = createObject<CMapObject>(name);
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
    addTile(createObject<CTile>(name), coords.x, coords.y, coords.z);
}

Coords CMap::getLocationByName(std::string name) {
    return this->getObjectByName(name)->getCoords();
}

std::shared_ptr<CPlayer> CMap::getPlayer() {
    return player;
}

void CMap::setPlayer(std::shared_ptr<CPlayer> player) {
    addObject(player);
    player->moveTo(entryx, entryy, entryz);
    this->player = player;
}

std::shared_ptr<CLootHandler> CMap::getLootHandler() {
    return lootHandler.get([this]() {
        return std::make_shared<CLootHandler>(this->ptr<CMap>());
    });
}

std::shared_ptr<CObjectHandler> CMap::getObjectHandler() {
    return objectHandler.get([this]() {
        return std::make_shared<CObjectHandler>(getGame()->getObjectHandler());
    });
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
}

bool CMap::addTile(std::shared_ptr<CTile> tile, int x, int y, int z) {
    if (this->contains(x, y, z)) {
        return false;
    }
    tiles.insert(std::make_pair(Coords(x, y, z), tile));
    tile->moveTo(x, y, z);
    return true;
}

void CMap::removeTile(int x, int y, int z) {
    this->tiles.erase(this->tiles.find(Coords(x, y, z)));
}

int CMap::getCurrentMap() {
    return currentLevel;
}

std::shared_ptr<CGame> CMap::getGame() const {
    return game.lock();
}

void CMap::mapUp() {
    currentLevel--;
}

void CMap::mapDown() {
    currentLevel++;
}

std::shared_ptr<CTile> CMap::getTile(int x, int y, int z) {
    Coords coords(x, y, z);
    std::shared_ptr<CTile> tile;
    auto it = this->tiles.find(coords);
    if (it == this->tiles.end()) {
        auto bound = boundaries[z];
        if (x < 0 || y < 0 || x > bound.first || y > bound.second) {
            tile = createObject<CTile>("MountainTile");
        } else {
            tile = createObject<CTile>(defaultTiles[z]);
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
    mapObject->setMap(this->ptr<CMap>());
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
}

void CMap::removeObject(std::shared_ptr<CMapObject> mapObject) {
    mapObjects.erase(mapObjects.find(mapObject->getName()));
    getEventHandler()->gameEvent(mapObject, std::make_shared<CGameEvent>(CGameEvent::Type::onDestroy));
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
    static std::shared_ptr<vstd::future<void, void>> move = vstd::later([]() {});
    auto map = this->ptr<CMap>();

    move = move->thenLater([map]() {
        vstd::wait_until([map]() {
            return !map->moving;
        });

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
        };

        //TODO: return future and replace
        vstd::join(map->mapObjects |
                   boost::adaptors::map_values |
                   boost::adaptors::filtered(pred) |
                   boost::adaptors::transformed(controller))
                ->thenLater(end_callback);
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

void CMap::load_plugin(std::function<std::shared_ptr<CMapPlugin>()> plugin) {
    plugin()->load(this->ptr<CMap>());
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

