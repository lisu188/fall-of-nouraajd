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
#include "core/CMap.h"
#include <algorithm>
#include "core/CController.h"
#include "core/CGame.h"
#include "object/CItem.h"
#include "object/CTrigger.h"

namespace {
int normalize_wrapped_axis(int value, int max_value) {
    const int size = max_value + 1;
    if (size <= 0) {
        return value;
    }
    int normalized = value % size;
    if (normalized < 0) {
        normalized += size;
    }
    return normalized;
}
} // namespace

std::map<int, std::pair<int, int>> CMap::getBounds() {
    std::map<int, std::pair<int, int>> bounds;
    for (const auto &[level, x_bound] : xBounds) {
        const int y_bound = vstd::ctn(yBounds, level) ? yBounds.at(level) : 0;
        bounds[level] = std::make_pair(x_bound, y_bound);
    }
    for (const auto &[level, y_bound] : yBounds) {
        if (!vstd::ctn(bounds, level)) {
            const int x_bound = vstd::ctn(xBounds, level) ? xBounds.at(level) : 0;
            bounds[level] = std::make_pair(x_bound, y_bound);
        }
    }
    return bounds;
}

std::map<int, int> CMap::getXBounds() { return xBounds; }

void CMap::setXBounds(std::map<int, int> bounds) { xBounds = std::move(bounds); }

std::map<int, int> CMap::getYBounds() { return yBounds; }

void CMap::setYBounds(std::map<int, int> bounds) { yBounds = std::move(bounds); }

std::map<int, std::string> CMap::getDefaultTiles() { return defaultTiles; }

void CMap::setDefaultTiles(std::map<int, std::string> tiles) { defaultTiles = std::move(tiles); }

std::map<int, std::string> CMap::getOutOfBoundsTiles() { return outOfBoundsTiles; }

void CMap::setOutOfBoundsTiles(std::map<int, std::string> tiles) { outOfBoundsTiles = std::move(tiles); }

std::map<int, int> CMap::getWrapX() { return wrapX; }

void CMap::setWrapX(std::map<int, int> values) { wrapX = std::move(values); }

std::map<int, int> CMap::getWrapY() { return wrapY; }

void CMap::setWrapY(std::map<int, int> values) { wrapY = std::move(values); }

void CMap::removeObjectByName(std::string name) { this->removeObject(this->getObjectByName(name)); }

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

Coords CMap::getLocationByName(std::string name) { return this->getObjectByName(name)->getCoords(); }

std::shared_ptr<CPlayer> CMap::getPlayer() {
    // TODO: think of better solution after save
    if (!player) {
        for (auto object : getObjects()) {
            if (object && object->getName() == "player") {
                player = vstd::cast<CPlayer>(object);
                player->setController(getGame()->createObject<CPlayerController>());
                player->setFightController(getGame()->createObject<CPlayerFightController>());
                registerPlayerTriggers();
                break;
            }
        }
    }
    return player;
}

void CMap::setPlayer(std::shared_ptr<CPlayer> player) {
    player->setName("player");
    player->setController(getGame()->createObject<CPlayerController>());
    player->setFightController(getGame()->createObject<CPlayerFightController>());
    this->player = player;
    registerPlayerTriggers();
    addObject(player);
    player->moveTo(entryx, entryy, entryz);
}

std::shared_ptr<CEventHandler> CMap::getEventHandler() {
    return eventHandler.get([this]() { return std::make_shared<CEventHandler>(); });
}

std::uint64_t CMap::getNavigationRevision() const { return navigationRevision; }

void CMap::bumpNavigationRevision() { navigationRevision++; }

void CMap::moveTile(std::shared_ptr<CTile> tile, int x, int y, int z) {
    Coords coords = normalizeCoords(tile->getCoords());
    Coords target = normalizeCoords(Coords(x, y, z));
    auto it = tiles.find(coords);
    if (it != tiles.end()) {
        tiles.erase(it);
    }
    tiles.insert(std::make_pair(target, tile));
    bumpNavigationRevision();
    signal("tileChanged", target);
}

bool CMap::addTile(std::shared_ptr<CTile> tile, int x, int y, int z) {
    if (!tile) {
        return false;
    }
    Coords coords = normalizeCoords(Coords(x, y, z));
    if (this->contains(coords.x, coords.y, coords.z)) {
        return false;
    }
    tile->setPosx(coords.x);
    tile->setPosy(coords.y);
    tile->setPosz(coords.z);
    tiles.insert(std::make_pair(coords, tile));
    bumpNavigationRevision();
    signal("tileChanged", coords);
    return true;
}

void CMap::removeTile(int x, int y, int z) {
    Coords coords = normalizeCoords(Coords(x, y, z));
    auto it = this->tiles.find(coords);
    if (it != this->tiles.end()) {
        this->tiles.erase(it);
    }
    bumpNavigationRevision();
    signal("tileChanged", coords);
}

std::shared_ptr<CTile> CMap::getTile(int x, int y, int z) {
    Coords coords = normalizeCoords(Coords(x, y, z));
    std::shared_ptr<CTile> tile;
    auto it = this->tiles.find(coords);
    if (it == this->tiles.end()) {
        if (hasBounds(z) && (coords.x < 0 || coords.y < 0 || coords.x > xBounds.at(z) || coords.y > yBounds.at(z))) {
            tile = getGame()->createObject<CTile>(vstd::ctn(outOfBoundsTiles, z) && !outOfBoundsTiles.at(z).empty()
                                                      ? outOfBoundsTiles.at(z)
                                                      : "MountainTile");
        } else {
            tile = getGame()->createObject<CTile>(
                vstd::ctn(defaultTiles, z) && !defaultTiles.at(z).empty() ? defaultTiles.at(z) : "GrassTile");
        }
        if (tile) {
            this->addTile(tile, coords.x, coords.y, coords.z);
        }
    } else {
        tile = (*it).second;
    }
    return tile;
}

std::shared_ptr<CTile> CMap::getTile(Coords coords) { return this->getTile(coords.x, coords.y, coords.z); }

bool CMap::canStep(int x, int y, int z) {
    Coords coords = normalizeCoords(Coords(x, y, z));
    auto it = this->tiles.find(coords);
    for (const auto &object : getObjectsAtCoords(coords)) {
        if (!object->getCanStep()) {
            return false;
        }
    }
    if (it != this->tiles.end()) {
        return (*it).second->canStep();
    }
    const int x_bound = vstd::ctn(xBounds, z) ? xBounds.at(z) : 0;
    const int y_bound = vstd::ctn(yBounds, z) ? yBounds.at(z) : 0;
    return !(coords.x < 0 || coords.y < 0 || coords.x > x_bound || coords.y > y_bound);
}

bool CMap::canStep(Coords coords) { return canStep(coords.x, coords.y, coords.z); }

int CMap::getMovementCost(int x, int y, int z) {
    getTile(x, y, z);
    return 1;
}

int CMap::getMovementCost(Coords coords) {
    coords = normalizeCoords(coords);
    return getMovementCost(coords.x, coords.y, coords.z);
}

bool CMap::contains(int x, int y, int z) {
    Coords coords = normalizeCoords(Coords(x, y, z));
    auto it = tiles.find(coords);
    return it != tiles.end();
}

void CMap::addObject(const std::shared_ptr<CMapObject> &mapObject) {
    vstd::fail_if(vstd::ctn(mapObjects, mapObject->getName()), "Map object already exists: " + mapObject->getName());
    std::shared_ptr<CCreature> creature = vstd::cast<CCreature>(mapObject);
    if (creature.get()) {
        if (creature->getLevel() == 0) {
            creature->addExp(0);
            creature->heal(0);
            creature->addMana(0);
        }
        creature->addExp(0);
    }
    mapObjects.insert(std::make_pair(mapObject->getName(), mapObject));
    bumpNavigationRevision();
    getEventHandler()->gameEvent(mapObject, std::make_shared<CGameEvent>(CGameEvent::Type::onCreate));
    signal("objectChanged", mapObject->getCoords());
}

void CMap::removeObject(const std::shared_ptr<CMapObject> &mapObject) {
    if (!mapObject) {
        return;
    }

    auto map_object_it = mapObjects.find(mapObject->getName());
    if (map_object_it == mapObjects.end()) {
        return;
    }

    mapObjects.erase(map_object_it);
    vstd::erase_if(mapObjectsCache, [mapObject](auto it) { return it.second == mapObject->getName(); });
    bumpNavigationRevision();
    getEventHandler()->gameEvent(mapObject, std::make_shared<CGameEvent>(CGameEvent::Type::onDestroy));
    signal("objectChanged", mapObject->getCoords());
}

int CMap::getEntryX() { return entryx; }

int CMap::getEntryY() { return entryy; }

int CMap::getEntryZ() { return entryz; }

void CMap::setEntryX(int x) { entryx = x; }

void CMap::setEntryY(int y) { entryy = y; }

void CMap::setEntryZ(int z) { entryz = z; }

std::shared_ptr<CMapObject> CMap::getObjectByName(const std::string &name) {
    auto it = mapObjects.find(name);
    if (it != mapObjects.end()) {
        return (*it).second;
    }
    return std::shared_ptr<CMapObject>();
}

bool CMap::isMoving() { return moving; }

// void CMap::applyEffects() {
//     auto pred = [](std::shared_ptr<CMapObject> object) {
//         return vstd::castable<CCreature>(object);
//     };
//     for (std::shared_ptr<CMapObject> object:mapObjects |
//                                             std::views::values |
//                                             std::views::filter(pred))
//                                             {
//         vstd::cast<CCreature>(object)->applyEffects();
//     }
// }

void CMap::forObjects(std::function<void(std::shared_ptr<CMapObject>)> func,
                      std::function<bool(std::shared_ptr<CMapObject>)> predicate) {
    auto clone = mapObjects;
    for (std::shared_ptr<CMapObject> object : clone | std::views::values | std::views::filter(predicate)) {
        func(object);
    }
}

void CMap::forTiles(std::function<void(std::shared_ptr<CTile>)> func,
                    std::function<bool(std::shared_ptr<CTile>)> predicate) {
    for (std::shared_ptr<CTile> tile : tiles | std::views::values | std::views::filter(predicate)) {
        func(tile);
    }
}

void CMap::removeObjects(std::function<bool(std::shared_ptr<CMapObject>)> func) {
    auto clone = mapObjects;
    for (std::shared_ptr<CMapObject> object : clone | std::views::values | std::views::filter(func)) {
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

    // TODO: map->applyEffects();

    map->forObjects([map](std::shared_ptr<CMapObject> mapObject) {
        map->getEventHandler()->gameEvent(mapObject, std::make_shared<CGameEvent>(CGameEvent::Type::onTurn));
    });

    auto is_active_creature = [map](const std::shared_ptr<CCreature> &creature) {
        return creature && creature->getMap() == map && map->getObjectByName(creature->getName()) == creature &&
               creature->isAlive();
    };

    auto should_interrupt_after_step = [map](const std::shared_ptr<CCreature> &creature, const Coords &target) {
        auto objects = map->getObjectsAtCoords(target);
        return std::any_of(objects.begin(), objects.end(), [&](const auto &object) {
            return object != creature &&
                   (vstd::cast<CCreature>(object) || (vstd::cast<Visitable>(object) && !vstd::cast<CItem>(object)));
        });
    };

    auto pred = [is_active_creature](std::shared_ptr<CMapObject> object) {
        auto creature = vstd::cast<CCreature>(object);
        return creature && vstd::castable<Moveable>(object) && is_active_creature(creature);
    };

    std::shared_ptr<std::list<std::pair<std::shared_ptr<CCreature>, Coords>>> coordinates =
        std::make_shared<std::list<std::pair<std::shared_ptr<CCreature>, Coords>>>();

    std::vector<std::shared_ptr<CMapObject>> active_objects;
    for (auto object : map->mapObjects | std::views::values | std::views::filter(pred)) {
        active_objects.push_back(object);
    }

    auto controller = [coordinates](std::shared_ptr<CMapObject> object) {
        auto creature = vstd::cast<CCreature>(object);
        return creature->getController()->control(creature)->thenLater(
            [creature, coordinates](Coords coords) { coordinates->push_back(std::make_pair(creature, coords)); });
    };

    std::vector<std::shared_ptr<vstd::future<void, Coords>>> pending;
    for (const auto &object : active_objects) {
        pending.push_back(controller(object));
    }
    auto joined = vstd::async([pending]() {
        for (const auto &future : pending) {
            future->get();
        }
        return std::set<void *>{};
    });

    bool round_complete = false;
    joined->thenLater([&round_complete](std::set<void *>) { round_complete = true; });
    vstd::wait_until([&round_complete]() { return round_complete; });

    for (auto [creature, coords] : *coordinates) {
        auto controller_ptr = creature->getController();
        if (!is_active_creature(creature)) {
            controller_ptr->interrupt(creature);
            continue;
        }

        auto current = map->normalizeCoords(creature->getCoords());
        auto target = map->normalizeCoords(coords);
        if (target == current) {
            controller_ptr->interrupt(creature);
            continue;
        }
        if (!map->canStep(target)) {
            controller_ptr->interrupt(creature);
            continue;
        }

        const bool interrupt_after_step = should_interrupt_after_step(creature, target);
        creature->moveTo(target);

        if (!is_active_creature(creature) || map->normalizeCoords(creature->getCoords()) != target) {
            controller_ptr->interrupt(creature);
            continue;
        }

        controller_ptr->onStepCommitted(creature, target);
        if (interrupt_after_step) {
            controller_ptr->interrupt(creature);
        }
    }

    map->forObjects(
        [](std::shared_ptr<CMapObject> object) {
            if (auto creature = vstd::cast<CCreature>(object)) {
                creature->getController()->onTurnEnded(creature);
            }
        },
        [](std::shared_ptr<CMapObject> object) { return vstd::castable<CCreature>(object); });

    map->moving = false;
    map->turn++;
    map->signal("turnPassed");
}

int CMap::getTurn() { return turn; }

void CMap::setTurn(int turn) { this->turn = turn; }

void CMap::setTiles(std::set<std::shared_ptr<CTile>> objects) {
    tiles.clear();
    for (const auto &ob : objects) {
        if (!ob) {
            continue;
        }
        tiles[normalizeCoords(ob->getCoords())] = ob;
    }
    bumpNavigationRevision();
}

std::set<std::shared_ptr<CTile>> CMap::getTiles() {
    std::set<std::shared_ptr<CTile>> result;
    for (const auto &[coords, tile] : tiles) {
        result.insert(tile);
    }
    return result;
}

void CMap::setObjects(std::set<std::shared_ptr<CMapObject>> objects) {
    mapObjects.clear();
    mapObjectsCache.clear();
    for (auto ob : objects) {
        if (!ob) {
            vstd::logger::warning("Ignoring null map object in CMap::setObjects");
            continue;
        }
        mapObjects[ob->getName()] = ob;
        mapObjectsCache.insert(std::make_pair(normalizeCoords(ob->getCoords()), ob->getName()));
    }
    bumpNavigationRevision();
}

std::set<std::shared_ptr<CMapObject>> CMap::getObjects() {
    std::set<std::shared_ptr<CMapObject>> result;
    for (const auto &[name, object] : mapObjects) {
        result.insert(object);
    }
    return result;
}

void CMap::dumpPaths(std::string path) {
    CPathFinder::saveMap(
        getPlayer()->getCoords(), [this](auto coords) { return this->canStep(coords); }, path,
        [this](auto coords) -> std::optional<Coords> {
            for (auto ob : getObjectsAtCoords(coords)) {
                if (ob->getBoolProperty("waypoint")) {
                    return Coords(ob->getNumericProperty("x"), ob->getNumericProperty("y"),
                                  ob->getNumericProperty("z"));
                }
            }
            return std::nullopt;
        },
        [this](auto coords) { return this->getAdjacentCoords(coords); },
        [this](auto from, auto to) { return this->getDistance(from, to); });
}

std::set<std::shared_ptr<CTrigger>> CMap::getTriggers() {
    std::set<std::shared_ptr<CTrigger>> triggers;
    for (const auto &trigger : getEventHandler()->getTriggers()) {
        if (!dynamic_cast<CCustomTrigger *>(trigger.get())) {
            triggers.insert(trigger);
        }
    }
    return triggers;
}

void CMap::setTriggers(std::set<std::shared_ptr<CTrigger>> triggers) {
    for (auto trigger : triggers) {
        if (!trigger) {
            vstd::logger::warning("Ignoring null trigger in CMap::setTriggers");
            continue;
        }
        getEventHandler()->registerTrigger(trigger);
    }
}

void CMap::setMapName(std::string mapName) { this->mapName = mapName; }

std::string CMap::getMapName() { return mapName; }

void CMap::objectMoved(const std::shared_ptr<CMapObject> &object, Coords _old, Coords _new) {
    _old = normalizeCoords(_old);
    _new = normalizeCoords(_new);
    vstd::erase_if(mapObjectsCache, [object](auto it) { return it.second == object->getName(); });

    mapObjectsCache.insert(std::make_pair(_new, object->getName()));
    bumpNavigationRevision();

    // TODO: check if it`s correct
    signal("objectChanged", _old);
    signal("objectChanged", _new);
}

std::set<std::shared_ptr<CMapObject>> CMap::getObjectsAtCoords(Coords coords) {
    coords = normalizeCoords(coords);
    std::set<std::shared_ptr<CMapObject>> ret;
    auto range = mapObjectsCache.equal_range(coords);
    for (auto it = range.first; it != range.second; it++) {
        if (auto ob = getObjectByName(it->second)) {
            ret.insert(ob);
        }
    }
    return ret;
}

void CMap::forObjectsAtCoords(Coords coords, std::function<void(std::shared_ptr<CMapObject>)> func,
                              std::function<bool(std::shared_ptr<CMapObject>)> predicate) {
    auto clone = getObjectsAtCoords(coords);
    for (auto object : clone) {
        if (predicate(object)) {
            func(object);
        }
    }
}

void CMap::addObject(const std::shared_ptr<CMapObject> &mapObject, Coords coords) {
    if (this->canStep(coords)) {
        if (mapObject) {
            addObject(mapObject);
            mapObject->moveTo(coords.x, coords.y, coords.z);
        }
    }
}

Coords CMap::getEntry() { return Coords(getEntryX(), getEntryY(), getEntryZ()); }

bool CMap::hasBounds(int z) const { return vstd::ctn(xBounds, z) && vstd::ctn(yBounds, z); }

int CMap::normalizeAxis(int value, int z, bool wrapAxis, const std::map<int, int> &bounds) const {
    if (!wrapAxis || !vstd::ctn(bounds, z)) {
        return value;
    }
    return normalize_wrapped_axis(value, bounds.at(z));
}

Coords CMap::normalizeCoords(Coords coords) const {
    coords.x = normalizeAxis(coords.x, coords.z, wrapsX(coords.z), xBounds);
    coords.y = normalizeAxis(coords.y, coords.z, wrapsY(coords.z), yBounds);
    return coords;
}

std::vector<Coords> CMap::getAdjacentCoords(Coords coords, bool includeSelf) const {
    std::vector<Coords> adjacent;
    adjacent.reserve(includeSelf ? 5 : 4);

    if (!wrapsX(coords.z) && !wrapsY(coords.z)) {
        if (includeSelf) {
            adjacent.push_back(coords);
        }
        adjacent.push_back(coords + EAST);
        adjacent.push_back(coords + WEST);
        adjacent.push_back(coords + SOUTH);
        adjacent.push_back(coords + NORTH);
        return adjacent;
    }

    auto add = [&adjacent, this](Coords candidate) {
        candidate = normalizeCoords(candidate);
        if (std::ranges::find(adjacent, candidate) == adjacent.end()) {
            adjacent.push_back(candidate);
        }
    };
    if (includeSelf) {
        add(coords);
    }
    add(coords + EAST);
    add(coords + WEST);
    add(coords + SOUTH);
    add(coords + NORTH);
    return adjacent;
}

Coords CMap::getShortestDelta(Coords from, Coords to) const {
    Coords normalized_from = normalizeCoords(from);
    Coords normalized_to = normalizeCoords(to);
    int dx = normalized_to.x - normalized_from.x;
    int dy = normalized_to.y - normalized_from.y;

    if (wrapsX(normalized_from.z) && vstd::ctn(xBounds, normalized_from.z)) {
        const int width = xBounds.at(normalized_from.z) + 1;
        if (std::abs(dx) > width / 2) {
            dx += dx > 0 ? -width : width;
        }
    }
    if (wrapsY(normalized_from.z) && vstd::ctn(yBounds, normalized_from.z)) {
        const int height = yBounds.at(normalized_from.z) + 1;
        if (std::abs(dy) > height / 2) {
            dy += dy > 0 ? -height : height;
        }
    }

    return Coords(dx, dy, normalized_to.z - normalized_from.z);
}

double CMap::getDistance(Coords from, Coords to) const { return getShortestDelta(from, to).getDist(ZERO); }

bool CMap::wrapsX(int z) const { return vstd::ctn(wrapX, z) && wrapX.at(z) != 0; }

bool CMap::wrapsY(int z) const { return vstd::ctn(wrapY, z) && wrapY.at(z) != 0; }

void CMap::registerPlayerTriggers() {
    if (playerTriggersRegistered) {
        return;
    }
    playerTriggersRegistered = true;

    auto restartTrigger = std::make_shared<CCustomTrigger>("player", "onDestroy", [](auto object, auto event) {
        auto _player = vstd::cast<CPlayer>(object);
        _player->getMap()->addObject(_player);
        _player->moveTo(object->getMap()->getEntryX(), object->getMap()->getEntryY(), object->getMap()->getEntryZ());
        _player->setHp(1);
    });

    auto turnTrigger = std::make_shared<CCustomTrigger>("player", "onTurn", [](auto object, auto event) {
        auto _player = vstd::cast<CPlayer>(object);
        _player->addMana(_player->getManaRegRate());
        _player->incTurn();
        _player->checkQuests();
    });

    getEventHandler()->registerTrigger(restartTrigger);
    getEventHandler()->registerTrigger(turnTrigger);
}
