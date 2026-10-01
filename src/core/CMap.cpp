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
#include "core/CNavigation.h"
#include <algorithm>
#include "core/CController.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CPlaytestTrace.h"
#include "core/CSceneManager.h"
#include "core/CSerialization.h"
#include "object/CItem.h"
#include "object/CCreature.h"
#include "object/CTrigger.h"

#include <atomic>
#include <chrono>
#include <limits>

namespace {
std::atomic_bool mapCoordinateLookupProbeEnabled{false};
std::atomic_size_t mapCoordinateLookupProbeCounter{0};

void recordCoordinateLookupProbe() {
    if (mapCoordinateLookupProbeEnabled.load(std::memory_order_relaxed)) {
        mapCoordinateLookupProbeCounter.fetch_add(1, std::memory_order_relaxed);
    }
}

int normalize_wrapped_axis(int value, int max_value) {
    const auto size = static_cast<std::int64_t>(max_value) + 1;
    if (size <= 0) {
        return value;
    }
    auto normalized = static_cast<std::int64_t>(value) % size;
    if (normalized < 0) {
        normalized += size;
    }
    return static_cast<int>(normalized);
}
} // namespace

CMap::~CMap() {
    const auto dyingMap = weak_from_this();
    for (const auto &[name, object] : mapObjects) {
        // A carried player can remain in this map's snapshot while already owned by its destination.
        if (object && !object->owningMap.owner_before(dyingMap) && !dyingMap.owner_before(object->owningMap)) {
            if (auto creature = vstd::cast<CCreature>(object)) {
                creature->releaseEffectReferences();
            }
        }
    }
}

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

void CMap::setXBounds(std::map<int, int> bounds) {
    std::lock_guard lock(navigationMutex);
    if (xBounds == bounds)
        return;
    if (navigationService && (!tiles.empty() || !mapObjects.empty() || !navigationEdges.empty()))
        navigationDomainCanonical = false;
    xBounds = std::move(bounds);
    routingChanged();
}

std::map<int, int> CMap::getYBounds() { return yBounds; }

void CMap::setYBounds(std::map<int, int> bounds) {
    std::lock_guard lock(navigationMutex);
    if (yBounds == bounds)
        return;
    if (navigationService && (!tiles.empty() || !mapObjects.empty() || !navigationEdges.empty()))
        navigationDomainCanonical = false;
    yBounds = std::move(bounds);
    routingChanged();
}

std::map<int, std::string> CMap::getDefaultTiles() { return defaultTiles; }

void CMap::setDefaultTiles(std::map<int, std::string> tiles) {
    std::lock_guard lock(navigationMutex);
    if (defaultTiles == tiles)
        return;
    defaultTiles = std::move(tiles);
    routingChanged();
}

std::map<int, std::string> CMap::getOutOfBoundsTiles() { return outOfBoundsTiles; }

void CMap::setOutOfBoundsTiles(std::map<int, std::string> tiles) {
    std::lock_guard lock(navigationMutex);
    if (outOfBoundsTiles == tiles)
        return;
    outOfBoundsTiles = std::move(tiles);
    routingChanged();
}

std::map<int, int> CMap::getWrapX() { return wrapX; }

void CMap::setWrapX(std::map<int, int> values) {
    std::lock_guard lock(navigationMutex);
    if (wrapX == values)
        return;
    if (navigationService && (!tiles.empty() || !mapObjects.empty() || !navigationEdges.empty()))
        navigationDomainCanonical = false;
    wrapX = std::move(values);
    routingChanged();
}

std::map<int, int> CMap::getWrapY() { return wrapY; }

void CMap::setWrapY(std::map<int, int> values) {
    std::lock_guard lock(navigationMutex);
    if (wrapY == values)
        return;
    if (navigationService && (!tiles.empty() || !mapObjects.empty() || !navigationEdges.empty()))
        navigationDomainCanonical = false;
    wrapY = std::move(values);
    routingChanged();
}

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

Coords CMap::getLocationByName(std::string name) {
    auto object = this->getObjectByName(name);
    return object ? object->getCoords() : ZERO;
}

std::shared_ptr<CPlayer> CMap::getPlayer() {
    // TODO: think of better solution after save
    if (!player) {
        for (auto object : getObjects()) {
            if (object && object->getName() == "player") {
                player = vstd::cast<CPlayer>(object);
                if (player) {
                    player->setController(getGame()->createObject<CPlayerController>());
                    player->setFightController(getGame()->createObject<CPlayerFightController>());
                    registerPlayerTriggers();
                }
                break;
            }
        }
    }
    return player;
}

void CMap::setPlayer(std::shared_ptr<CPlayer> player) {
    if (!player) {
        vstd::logger::warning("Ignoring null player assignment");
        return;
    }
    player->setOwningMap(this->ptr<CMap>());
    player->setName("player");
    player->setController(getGame()->createObject<CPlayerController>());
    player->setFightController(getGame()->createObject<CPlayerFightController>());
    this->player = player;
    registerPlayerTriggers();
    addObject(player);
    player->moveTo(entryx, entryy, entryz);
}

std::shared_ptr<CPlayer> CMap::detachPlayer() {
    auto detachedPlayer = player ? player : vstd::cast<CPlayer>(getObjectByName("player"));
    auto canonicalPlayer = vstd::cast<CPlayer>(getObjectByName("player"));
    if (!detachedPlayer && !canonicalPlayer) {
        return nullptr;
    }

    if (detachedPlayer) {
        removeObjectWithoutEvents(detachedPlayer);
    }
    if (canonicalPlayer && canonicalPlayer != detachedPlayer) {
        removeObjectWithoutEvents(canonicalPlayer);
    }
    if (detachedPlayer) {
        detachedPlayer->clearOwningMap(this->ptr<CMap>());
    }
    player.reset();
    return detachedPlayer ? detachedPlayer : canonicalPlayer;
}

void CMap::attachPlayer(std::shared_ptr<CPlayer> player) { attachPlayer(std::move(player), getEntry()); }

void CMap::attachPlayer(std::shared_ptr<CPlayer> player, Coords coords) {
    if (!player) {
        vstd::logger::warning("Ignoring null player attachment");
        return;
    }

    auto existingCanonicalObject = getObjectByName("player");
    if (existingCanonicalObject && existingCanonicalObject != player) {
        removeObjectWithoutEvents(existingCanonicalObject);
    }
    if (this->player && this->player != player) {
        removeObjectWithoutEvents(this->player);
    }

    auto map = this->ptr<CMap>();
    player->setOwningMap(map);
    player->setName("player");
    player->setController(getGame()->createObject<CPlayerController>());
    player->setFightController(getGame()->createObject<CPlayerFightController>());
    this->player = player;
    registerPlayerTriggers();

    const auto target = normalizeCoords(coords);
    if (getObjectByName("player") == player) {
        player->moveTo(target);
        return;
    }

    addObject(player);
    player->moveTo(target);
}

bool CMap::restorePlayerAfterLoad(std::string &error) {
    std::shared_ptr<CPlayer> restoredPlayer;
    int restoredPlayerCount = 0;
    for (const auto &object : getObjects()) {
        if (auto loadedPlayer = std::dynamic_pointer_cast<CPlayer>(object)) {
            restoredPlayerCount++;
            if (object->getName() != "player") {
                error = "saved player object is not named player";
                return false;
            }
            if (restoredPlayer) {
                error = "saved map contains multiple player objects";
                return false;
            }
            restoredPlayer = loadedPlayer;
        }
    }

    if (!restoredPlayer) {
        error = restoredPlayerCount == 0 ? "saved map does not contain a player object" : "saved player is invalid";
        return false;
    }

    if (!std::dynamic_pointer_cast<CPlayerController>(restoredPlayer->getController())) {
        restoredPlayer->setController(getGame()->createObject<CPlayerController>());
    }
    if (!std::dynamic_pointer_cast<CPlayerFightController>(restoredPlayer->getFightController())) {
        restoredPlayer->setFightController(getGame()->createObject<CPlayerFightController>());
    }
    player = restoredPlayer;
    registerPlayerTriggers();
    return true;
}

std::shared_ptr<CEventHandler> CMap::getEventHandler() {
    return eventHandler.get([this]() { return std::make_shared<CEventHandler>(); });
}

std::uint64_t CMap::getNavigationRevision() const { return navigationRevision; }

std::recursive_mutex &CMap::getNavigationMutex() const { return navigationMutex; }

std::uint64_t CMap::getRoutingEpoch() const {
    std::lock_guard lock(navigationMutex);
    auto game = const_cast<CMap *>(this)->getGame();
    auto revision = game ? game->getObjectHandler()->getNavigationConfigRevision() : 0;
    if (revision != routingConfigRevision) {
        routingConfigRevision = revision;
        const_cast<CMap *>(this)->routingChanged();
    }
    return routingEpoch;
}

std::shared_ptr<CNavigationService> CMap::getNavigationService() {
    std::lock_guard lock(navigationMutex);
    if (!navigationService) {
        auto game = getGame();
        navigationService = game ? game->getNavigationService() : std::make_shared<CNavigationService>();
    }
    return navigationService;
}

void CMap::includeNavigationTile(Coords coords) {
    auto end = navigationTileExtents.begin() + navigationTileExtentCount;
    auto found =
        std::find_if(navigationTileExtents.begin(), end, [&](const auto &entry) { return entry.level == coords.z; });
    if (found == end) {
        if (navigationTileExtentCount == navigationTileExtents.size()) {
            navigationTileExtentOverflow = true;
            return;
        }
        *found = {coords.z, {coords.x, coords.x, coords.y, coords.y}};
        ++navigationTileExtentCount;
        return;
    }
    auto &extent = found->extent;
    extent[0] = std::min(extent[0], coords.x);
    extent[1] = std::max(extent[1], coords.x);
    extent[2] = std::min(extent[2], coords.y);
    extent[3] = std::max(extent[3], coords.y);
}

void CMap::routingChanged(std::optional<Coords> coords) {
    ++routingEpoch;
    if (navigationService)
        navigationService->recordChange(ptr<CMap>(), routingEpoch, coords);
}

void CMap::navigationCellChanged(Coords coords) {
    std::lock_guard lock(navigationMutex);
    routingChanged(normalizeCoords(coords));
}

bool CMap::hasRegisteredTile(const CTile *tile) const {
    std::lock_guard lock(navigationMutex);
    auto coords = normalizeCoords(Coords(tile->getPosx(), tile->getPosy(), tile->getPosz()));
    auto found = tiles.find(coords);
    return found != tiles.end() && found->second.get() == tile;
}

CNavigationCell CMap::lookupNavigationCell(Coords coords, std::optional<CNavigationCell> fallback) {
    std::unique_lock lock(navigationMutex);
    coords = normalizeCoords(coords);
    const auto epoch = getRoutingEpoch();
    CNavigationCell result;
    auto tile = tiles.find(coords);
    if (tile != tiles.end() && tile->second) {
        result = {tile->second->canStep(), tile->second->getMovementCost()};
    } else if (fallback) {
        result = *fallback;
    } else {
        // Factories may execute Python and release its GIL; never keep the map lock across them.
        lock.unlock();
        auto value = resolveTileForLookup(coords);
        lock.lock();
        if (getRoutingEpoch() != epoch)
            return {};
        auto current = tiles.find(coords);
        if (current != tiles.end() && current->second)
            value = current->second;
        if (value) {
            result = {value->canStep(), value->getMovementCost()};
        } else if (!getGame()) {
            const int x = xBounds.contains(coords.z) ? xBounds.at(coords.z) : 0;
            const int y = yBounds.contains(coords.z) ? yBounds.at(coords.z) : 0;
            result = {coords.x >= 0 && coords.y >= 0 && coords.x <= x && coords.y <= y, 1};
        }
    }
    if (result.walkable) {
        const auto range = mapObjectsCache.equal_range(coords);
        for (auto it = range.first; it != range.second; ++it) {
            recordCoordinateLookupProbe();
            auto object = mapObjects.find(it->second);
            if (object != mapObjects.end() && object->second && !object->second->getCanStep()) {
                result.walkable = false;
                break;
            }
        }
    }
    result.cost = std::max(1, result.cost);
    return result;
}

const std::vector<CNavigationEdge> &CMap::getNavigationEdges() const { return navigationEdges; }

std::vector<Coords> CMap::getNavigationNeighbors(Coords coords, bool includeSelf) const {
    coords = normalizeCoords(coords);
    auto neighbors = getAdjacentCoords(coords, includeSelf);

    auto add_unique = [&neighbors, this](Coords candidate) {
        candidate = normalizeCoords(candidate);
        if (std::ranges::find(neighbors, candidate) == neighbors.end()) {
            neighbors.push_back(candidate);
        }
    };

    for (const auto &edge : navigationEdges) {
        if (!edge.enabled) {
            continue;
        }
        if (edge.source == coords) {
            add_unique(edge.target);
        } else if (edge.bidirectional && edge.target == coords) {
            add_unique(edge.source);
        }
    }

    return neighbors;
}

void CMap::registerNavigationEdge(CNavigationEdge edge) {
    std::lock_guard lock(navigationMutex);
    edge.source = normalizeCoords(edge.source);
    edge.target = normalizeCoords(edge.target);
    edge.movementCost = std::max(1, edge.movementCost);
    navigationEdges.push_back(std::move(edge));
    bumpNavigationRevision();
    routingChanged();
}

void CMap::addNavigationEdge(CNavigationEdge edge) { registerNavigationEdge(std::move(edge)); }

bool CMap::removeNavigationEdge(Coords source, Coords target, std::optional<std::string> sourceObjectName) {
    std::lock_guard lock(navigationMutex);
    source = normalizeCoords(source);
    target = normalizeCoords(target);
    auto it = std::ranges::find_if(navigationEdges, [&](const CNavigationEdge &edge) {
        return edge.source == source && edge.target == target && edge.sourceObjectName == sourceObjectName;
    });
    if (it == navigationEdges.end()) {
        return false;
    }
    navigationEdges.erase(it);
    bumpNavigationRevision();
    routingChanged();
    return true;
}

std::size_t CMap::unregisterNavigationEdgesForObject(const std::string &sourceObjectName) {
    std::lock_guard lock(navigationMutex);
    const auto old_size = navigationEdges.size();
    navigationEdges.erase(std::remove_if(navigationEdges.begin(), navigationEdges.end(),
                                         [&](const CNavigationEdge &edge) {
                                             return edge.sourceObjectName && *edge.sourceObjectName == sourceObjectName;
                                         }),
                          navigationEdges.end());
    const auto removed = old_size - navigationEdges.size();
    if (removed > 0) {
        bumpNavigationRevision();
        routingChanged();
    }
    return removed;
}

std::size_t CMap::getObjectCacheEntryCountForTesting() const { return mapObjectsCache.size(); }

void performance_guard::resetMapCoordinateLookupProbe() {
    mapCoordinateLookupProbeCounter.store(0, std::memory_order_relaxed);
    mapCoordinateLookupProbeEnabled.store(true, std::memory_order_relaxed);
}

std::size_t performance_guard::mapCoordinateLookupProbeCount() {
    return mapCoordinateLookupProbeCounter.load(std::memory_order_relaxed);
}

void performance_guard::disableMapCoordinateLookupProbe() {
    mapCoordinateLookupProbeEnabled.store(false, std::memory_order_relaxed);
}

void CMap::bumpNavigationRevision() {
    navigationRevision++;
    recordDirectPropertyChanged("navigationRevision");
}

void CMap::moveTile(std::shared_ptr<CTile> tile, int x, int y, int z) {
    std::lock_guard lock(navigationMutex);
    if (!tile) {
        return;
    }
    Coords coords = normalizeCoords(tile->getCoords());
    Coords target = normalizeCoords(Coords(x, y, z));
    auto source = tiles.find(coords);
    if (source == tiles.end() || source->second != tile) {
        return;
    }
    if (coords == target) {
        tile->setOwningMap(this->ptr<CMap>());
        tile->setXYZ(target.x, target.y, target.z);
        return;
    }
    if (!tiles.emplace(target, tile).second) {
        return;
    }

    tiles.erase(coords);
    includeNavigationTile(target);
    tile->setOwningMap(this->ptr<CMap>());
    tile->setXYZ(target.x, target.y, target.z);
    bumpNavigationRevision();
    routingChanged(coords);
    routingChanged(target);
    recordDirectPropertyChanged("tiles");
    signal("tileChanged", target);
}

bool CMap::addTile(std::shared_ptr<CTile> tile, int x, int y, int z) {
    std::lock_guard lock(navigationMutex);
    if (!tile) {
        return false;
    }
    Coords coords = normalizeCoords(Coords(x, y, z));
    if (this->contains(coords.x, coords.y, coords.z)) {
        return false;
    }
    tile->setOwningMap(this->ptr<CMap>());
    tile->setXYZ(coords.x, coords.y, coords.z);
    tiles.insert(std::make_pair(coords, tile));
    includeNavigationTile(coords);
    bumpNavigationRevision();
    routingChanged(coords);
    recordDirectPropertyChanged("tiles");
    signal("tileChanged", coords);
    return true;
}

void CMap::removeTile(int x, int y, int z) {
    std::lock_guard lock(navigationMutex);
    Coords coords = normalizeCoords(Coords(x, y, z));
    auto it = this->tiles.find(coords);
    if (it != this->tiles.end()) {
        auto tile = it->second;
        this->tiles.erase(it);
        if (tile) {
            tile->clearOwningMap(this->ptr<CMap>());
        }
    }
    bumpNavigationRevision();
    routingChanged(coords);
    recordDirectPropertyChanged("tiles");
    signal("tileChanged", coords);
}

std::shared_ptr<CTile> CMap::getTile(int x, int y, int z) {
    Coords coords;
    {
        std::lock_guard lock(navigationMutex);
        coords = normalizeCoords(Coords(x, y, z));
        auto found = tiles.find(coords);
        if (found != tiles.end())
            return found->second;
    }
    auto tile = resolveTileForLookup(coords);
    if (tile && !addTile(tile, coords.x, coords.y, coords.z)) {
        std::lock_guard lock(navigationMutex);
        auto found = tiles.find(normalizeCoords(coords));
        return found != tiles.end() ? found->second : nullptr;
    }
    return tile;
}

std::shared_ptr<CTile> CMap::getTile(Coords coords) { return getTile(coords.x, coords.y, coords.z); }

bool CMap::canStep(int x, int y, int z) { return lookupNavigationCell(Coords(x, y, z), std::nullopt).walkable; }

bool CMap::canStep(Coords coords) { return canStep(coords.x, coords.y, coords.z); }

int CMap::getMovementCost(int x, int y, int z) {
    auto tile = getTile(x, y, z);
    return tile ? std::max(1, tile->getMovementCost()) : 1;
}

int CMap::getMovementCost(Coords coords) {
    coords = normalizeCoords(coords);
    return getMovementCost(coords.x, coords.y, coords.z);
}

int CMap::lookupMovementCost(int x, int y, int z) {
    auto tile = resolveTileForLookup(Coords(x, y, z));
    return tile ? std::max(1, tile->getMovementCost()) : 1;
}

int CMap::lookupMovementCost(Coords coords) { return lookupMovementCost(coords.x, coords.y, coords.z); }

std::int64_t CMap::lookupNavigationStepCost(Coords from, Coords to) {
    int fee = std::numeric_limits<int>::max();
    bool matched = false;
    {
        std::lock_guard lock(navigationMutex);
        from = normalizeCoords(from);
        to = normalizeCoords(to);
        if (!navigationEdges.empty()) {
            const auto adjacent = getAdjacentCoords(from);
            if (std::ranges::find(adjacent, to) == adjacent.end()) {
                for (const auto &edge : navigationEdges) {
                    if (edge.enabled &&
                        ((edge.source == from && normalizeCoords(edge.target) == to) ||
                         (edge.bidirectional && edge.target == from && normalizeCoords(edge.source) == to))) {
                        matched = true;
                        fee = std::min(fee, std::max(1, edge.movementCost));
                    }
                }
            }
        }
    }
    const std::int64_t terrain_cost = lookupMovementCost(to);
    return matched ? terrain_cost + fee - 1 : terrain_cost;
}

bool CMap::contains(int x, int y, int z) {
    Coords coords = normalizeCoords(Coords(x, y, z));
    auto it = tiles.find(coords);
    return it != tiles.end();
}

void CMap::addObject(const std::shared_ptr<CMapObject> &mapObject) {
    std::optional<pybind11::gil_scoped_acquire> gil;
    if (Py_IsInitialized())
        gil.emplace();
    std::unique_lock lock(navigationMutex);
    if (!mapObject) {
        vstd::logger::warning("Ignoring null map object");
        return;
    }
    if (vstd::ctn(mapObjects, mapObject->getName())) {
        vstd::logger::warning("Ignoring duplicate map object:", mapObject->getName());
        return;
    }
    std::shared_ptr<CCreature> creature = vstd::cast<CCreature>(mapObject);
    mapObject->setOwningMap(this->ptr<CMap>());
    lock.unlock();
    if (creature.get()) {
        if (creature->getLevel() == 0) {
            creature->addExp(0);
            creature->heal(0);
            creature->addMana(0);
        }
        creature->addExp(0);
    }
    lock.lock();
    if (vstd::ctn(mapObjects, mapObject->getName())) {
        if (mapObjects.at(mapObject->getName()) != mapObject)
            mapObject->clearOwningMap(this->ptr<CMap>());
        vstd::logger::warning("Ignoring duplicate map object after initialization:", mapObject->getName());
        return;
    }
    mapObjects.insert(std::make_pair(mapObject->getName(), mapObject));
    mapObjectsCache.insert(std::make_pair(normalizeCoords(mapObject->getCoords()), mapObject->getName()));
    bumpNavigationRevision();
    if (!mapObject->getCanStep())
        routingChanged(mapObject->getCoords());
    recordDirectPropertyChanged("objects");
    lock.unlock();
    getEventHandler()->gameEvent(mapObject, std::make_shared<CGameEvent>(CGameEvent::CType::onCreate));
    signal("objectChanged", mapObject->getCoords());
}

void CMap::removeObject(const std::shared_ptr<CMapObject> &mapObject) {
    std::optional<pybind11::gil_scoped_acquire> gil;
    if (Py_IsInitialized())
        gil.emplace();
    std::unique_lock lock(navigationMutex);
    if (!mapObject) {
        return;
    }

    auto map_object_it = mapObjects.find(mapObject->getName());
    if (map_object_it == mapObjects.end() || map_object_it->second != mapObject) {
        return;
    }

    mapObjects.erase(map_object_it);
    vstd::erase_if(mapObjectsCache, [mapObject](auto it) { return it.second == mapObject->getName(); });
    bumpNavigationRevision();
    if (!mapObject->getCanStep())
        routingChanged(mapObject->getCoords());
    recordDirectPropertyChanged("objects");
    lock.unlock();
    getEventHandler()->gameEvent(mapObject, std::make_shared<CGameEvent>(CGameEvent::CType::onDestroy));
    lock.lock();
    auto current_object_it = mapObjects.find(mapObject->getName());
    if (current_object_it == mapObjects.end() || current_object_it->second != mapObject) {
        mapObject->clearOwningMap(this->ptr<CMap>());
    }
    lock.unlock();
    signal("objectChanged", mapObject->getCoords());
}

bool CMap::removeObjectWithoutEvents(const std::shared_ptr<CMapObject> &mapObject) {
    std::lock_guard lock(navigationMutex);
    if (!mapObject) {
        return false;
    }

    auto map_object_it = std::ranges::find_if(mapObjects, [&](const auto &entry) { return entry.second == mapObject; });
    if (map_object_it == mapObjects.end()) {
        return false;
    }

    const auto registeredName = map_object_it->first;
    const auto coords = mapObject->getCoords();
    mapObjects.erase(map_object_it);
    vstd::erase_if(mapObjectsCache, [&registeredName](auto it) { return it.second == registeredName; });
    mapObject->clearOwningMap(this->ptr<CMap>());
    bumpNavigationRevision();
    if (!mapObject->getCanStep())
        routingChanged(mapObject->getCoords());
    recordDirectPropertyChanged("objects");
    signal("objectChanged", coords);
    return true;
}

int CMap::getEntryX() { return entryx; }

int CMap::getEntryY() { return entryy; }

int CMap::getEntryZ() { return entryz; }

void CMap::setEntryX(int x) { entryx = x; }

void CMap::setEntryY(int y) { entryy = y; }

void CMap::setEntryZ(int z) { entryz = z; }

std::shared_ptr<CMapObject> CMap::getObjectByName(const std::string &name) {
    std::lock_guard lock(navigationMutex);
    auto it = mapObjects.find(name);
    if (it != mapObjects.end()) {
        return (*it).second;
    }
    return std::shared_ptr<CMapObject>();
}

bool CMap::isMoving() { return moving; }

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

    auto game = map->getGame();
    // Do not begin a new movement/controller cycle once a map transition has been queued. The
    // pending transition will swap the active map, so running another turn on the old map would
    // only schedule controller futures whose results must then be discarded as stale.
    if (auto sceneManager = game ? game->getSceneManager() : nullptr;
        sceneManager && sceneManager->isTransitionPending()) {
        return;
    }

    map->moving = true;

    try {
        vstd::logger::debug("Turn:", map->turn);

        auto transitionContext = game ? game->getContext() : nullptr;
        const auto expectedGeneration = transitionContext ? transitionContext->captureTransitionGeneration()
                                                          : CGameContext::TransitionGeneration{0};
        auto canApplyDeferredMoveWork = [map, transitionContext, expectedGeneration]() {
            if (transitionContext && !transitionContext->isTransitionGenerationCurrent(expectedGeneration)) {
                return false;
            }
            auto game = map->getGame();
            return !game || game->getMap() == map;
        };

        map->forObjects([map](std::shared_ptr<CMapObject> mapObject) {
            map->getEventHandler()->gameEvent(mapObject, std::make_shared<CGameEvent>(CGameEvent::CType::onTurn));
        });

        auto is_active_creature = [map](const std::shared_ptr<CCreature> &creature) {
            return creature && creature->getMap() == map && map->getObjectByName(creature->getName()) == creature &&
                   creature->isAlive();
        };

        auto should_interrupt_after_step = [map](const std::shared_ptr<CCreature> &creature, const Coords &target) {
            auto objects = map->getObjectsAtCoords(target);
            return std::any_of(objects.begin(), objects.end(), [&](const auto &object) {
                return object != creature && (vstd::cast<CCreature>(object) ||
                                              (vstd::cast<CVisitable>(object) && !vstd::cast<CItem>(object)));
            });
        };

        auto pred = [is_active_creature](std::shared_ptr<CMapObject> object) {
            auto creature = vstd::cast<CCreature>(object);
            return creature && vstd::castable<CMoveable>(object) && is_active_creature(creature);
        };

        std::vector<std::shared_ptr<CCreature>> plannedCreatures;
        std::vector<std::shared_ptr<vstd::future<Coords, void>>> pending;
        for (auto object : map->mapObjects | std::views::values | std::views::filter(pred)) {
            auto creature = vstd::cast<CCreature>(object);
            plannedCreatures.push_back(creature);
            pending.push_back(creature->getController()->control(creature));
        }

        auto plannedFuture = vstd::when_all(pending);
        auto loop = vstd::event_loop<>::instance();
        while (!plannedFuture->isReady()) {
            if (loop->runPostedTasks() == 0) {
                if (Py_IsInitialized() && PyGILState_Check()) {
                    pybind11::gil_scoped_release release;
                    plannedFuture->waitFor(std::chrono::milliseconds(1));
                } else {
                    plannedFuture->waitFor(std::chrono::milliseconds(1));
                }
            }
        }
        auto plannedCoordinates = plannedFuture->get();
        std::list<std::pair<std::shared_ptr<CCreature>, Coords>> coordinates;
        if (canApplyDeferredMoveWork()) {
            for (std::size_t index = 0; index < plannedCoordinates.size(); ++index) {
                coordinates.emplace_back(plannedCreatures[index], plannedCoordinates[index]);
            }
        }

        for (auto [creature, coords] : coordinates) {
            if (!canApplyDeferredMoveWork()) {
                break;
            }
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
        map->recordDirectPropertyChanged("turn");
        map->signal("turnPassed");
    } catch (...) {
        map->moving = false;
        throw;
    }
}

int CMap::getTurn() { return turn; }

void CMap::setTurn(int turn) {
    this->turn = turn;
    recordDirectPropertyChanged("turn");
}

void CMap::setTiles(std::set<std::shared_ptr<CTile>> objects) {
    std::lock_guard lock(navigationMutex);
    auto map = this->ptr<CMap>();
    for (const auto &[coords, tile] : tiles) {
        if (tile) {
            tile->clearOwningMap(map);
        }
    }
    tiles.clear();
    navigationTileExtentCount = 0;
    navigationTileExtentOverflow = false;
    for (const auto &ob : objects) {
        if (!ob) {
            continue;
        }
        ob->setOwningMap(map);
        auto coords = normalizeCoords(ob->getCoords());
        tiles[coords] = ob;
        includeNavigationTile(coords);
    }
    bumpNavigationRevision();
    routingChanged();
    recordDirectPropertyChanged("tiles");
}

std::set<std::shared_ptr<CTile>> CMap::getTiles() {
    std::set<std::shared_ptr<CTile>> result;
    for (const auto &[coords, tile] : tiles) {
        result.insert(tile);
    }
    return result;
}

void CMap::setObjects(std::set<std::shared_ptr<CMapObject>> objects) {
    std::lock_guard lock(navigationMutex);
    if (CSerialization::isStrict()) {
        std::set<std::string> names;
        for (const auto &ob : objects) {
            if (!ob) {
                throw std::runtime_error("Saved map contains null object");
            }
            if (ob->getName().empty()) {
                throw std::runtime_error("Saved map contains object with empty name");
            }
            if (!names.insert(ob->getName()).second) {
                throw std::runtime_error("Saved map contains duplicate object name: " + ob->getName());
            }
        }
    }
    auto map = this->ptr<CMap>();
    for (const auto &[name, object] : mapObjects) {
        if (object) {
            object->clearOwningMap(map);
        }
    }
    mapObjects.clear();
    mapObjectsCache.clear();
    for (auto ob : objects) {
        if (!ob) {
            vstd::logger::warning("Ignoring null map object in CMap::setObjects");
            continue;
        }
        ob->setOwningMap(map);
        mapObjects[ob->getName()] = ob;
        mapObjectsCache.insert(std::make_pair(normalizeCoords(ob->getCoords()), ob->getName()));
    }
    bumpNavigationRevision();
    routingChanged();
    recordDirectPropertyChanged("objects");
}

std::set<std::shared_ptr<CMapObject>> CMap::getObjects() {
    std::set<std::shared_ptr<CMapObject>> result;
    for (const auto &[name, object] : mapObjects) {
        result.insert(object);
    }
    return result;
}

void CMap::dumpPaths(std::string path) {
    auto currentPlayer = getPlayer();
    if (!currentPlayer) {
        vstd::logger::warning("Cannot dump paths without a player");
        return;
    }
    CPathFinder::saveMap(
        currentPlayer->getCoords(), [this](auto coords) { return this->canStep(coords); }, path,
        [](auto) -> std::optional<Coords> { return std::nullopt; },
        [this](auto coords) { return this->getNavigationNeighbors(coords); },
        CPathFinder::mapHeuristic(this->ptr<CMap>()),
        [this](auto from, auto to) { return this->lookupNavigationStepCost(from, to); });
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

std::string CMap::getCombatHistory() { return combatHistory; }

void CMap::setCombatHistory(std::string history) { combatHistory = std::move(history); }

void CMap::objectMoved(const std::shared_ptr<CMapObject> &object, Coords _old, Coords _new) {
    std::lock_guard lock(navigationMutex);
    if (!object) {
        return;
    }
    _old = normalizeCoords(_old);
    _new = normalizeCoords(_new);
    if (CPlaytestTrace::enabled() && _old != _new) {
        json fields = {
            {"committed", true},
            {"from", CPlaytestTrace::coords(_old)},
            {"object", CPlaytestTrace::objectRef(object)},
            {"to", CPlaytestTrace::coords(_new)},
        };
        CPlaytestTrace::addMapContext(fields, this->ptr<CMap>());
        CPlaytestTrace::record("movement", fields);
    }
    auto range = mapObjectsCache.equal_range(_old);
    for (auto it = range.first; it != range.second;) {
        if (it->second == object->getName())
            it = mapObjectsCache.erase(it);
        else
            ++it;
    }

    mapObjectsCache.insert(std::make_pair(_new, object->getName()));
    bumpNavigationRevision();
    if (!object->getCanStep() && _old != _new) {
        routingChanged(_old);
        routingChanged(_new);
    }
    recordDirectPropertyChanged("objects");

    // TODO: check if it`s correct
    signal("objectChanged", _old);
    signal("objectChanged", _new);
}

std::set<std::shared_ptr<CMapObject>> CMap::getObjectsAtCoords(Coords coords) {
    std::lock_guard lock(navigationMutex);
    coords = normalizeCoords(coords);
    std::set<std::shared_ptr<CMapObject>> ret;
    auto range = mapObjectsCache.equal_range(coords);
    for (auto it = range.first; it != range.second; it++) {
        recordCoordinateLookupProbe();
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

bool CMap::isOutOfBounds(Coords coords) const {
    return hasBounds(coords.z) &&
           (coords.x < 0 || coords.y < 0 || coords.x > xBounds.at(coords.z) || coords.y > yBounds.at(coords.z));
}

bool CMap::isWithinBounds(Coords coords) const { return !isOutOfBounds(normalizeCoords(coords)); }

std::string CMap::fallbackTileType(Coords coords) const {
    if (isOutOfBounds(coords)) {
        return vstd::ctn(outOfBoundsTiles, coords.z) && !outOfBoundsTiles.at(coords.z).empty()
                   ? outOfBoundsTiles.at(coords.z)
                   : "MountainTile";
    }
    return vstd::ctn(defaultTiles, coords.z) && !defaultTiles.at(coords.z).empty() ? defaultTiles.at(coords.z)
                                                                                   : "GrassTile";
}

std::shared_ptr<CTile> CMap::resolveTileForLookup(Coords coords) {
    std::shared_ptr<CGame> game;
    std::string type;
    {
        std::lock_guard lock(navigationMutex);
        coords = normalizeCoords(coords);
        auto found = tiles.find(coords);
        if (found != tiles.end())
            return found->second;
        game = getGame();
        type = fallbackTileType(coords);
    }
    if (!game)
        return nullptr;
    std::optional<pybind11::gil_scoped_acquire> gil;
    if (Py_IsInitialized())
        gil.emplace();
    return game->createObject<CTile>(type);
}

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
    auto add = [&](Coords candidate) {
        candidate = normalizeCoords(candidate);
        if (std::ranges::find(adjacent, candidate) == adjacent.end())
            adjacent.push_back(candidate);
    };
    if (includeSelf)
        add(coords);
    for (auto delta : {EAST, WEST, SOUTH, NORTH}) {
        auto x = static_cast<std::int64_t>(coords.x) + delta.x;
        auto y = static_cast<std::int64_t>(coords.y) + delta.y;
        if (wrapsX(coords.z) && xBounds.contains(coords.z) && xBounds.at(coords.z) >= 0) {
            auto size = static_cast<std::int64_t>(xBounds.at(coords.z)) + 1;
            x = (x % size + size) % size;
        }
        if (wrapsY(coords.z) && yBounds.contains(coords.z) && yBounds.at(coords.z) >= 0) {
            auto size = static_cast<std::int64_t>(yBounds.at(coords.z)) + 1;
            y = (y % size + size) % size;
        }
        if (x >= INT_MIN && x <= INT_MAX && y >= INT_MIN && y <= INT_MAX)
            add(Coords(static_cast<int>(x), static_cast<int>(y), coords.z));
    }
    return adjacent;
}

Coords CMap::getShortestDelta(Coords from, Coords to) const {
    const auto normalized_from = normalizeCoords(from);
    const auto normalized_to = normalizeCoords(to);
    auto dx = static_cast<std::int64_t>(normalized_to.x) - normalized_from.x;
    auto dy = static_cast<std::int64_t>(normalized_to.y) - normalized_from.y;

    if (wrapsX(normalized_from.z) && xBounds.contains(normalized_from.z)) {
        const auto width = static_cast<std::int64_t>(xBounds.at(normalized_from.z)) + 1;
        if (width > 0 && std::abs(dx) > width / 2)
            dx += dx > 0 ? -width : width;
    }
    if (wrapsY(normalized_from.z) && yBounds.contains(normalized_from.z)) {
        const auto height = static_cast<std::int64_t>(yBounds.at(normalized_from.z)) + 1;
        if (height > 0 && std::abs(dy) > height / 2)
            dy += dy > 0 ? -height : height;
    }

    auto narrow = [](std::int64_t value) {
        return static_cast<int>(std::clamp<std::int64_t>(value, INT_MIN, INT_MAX));
    };
    return Coords(narrow(dx), narrow(dy), narrow(static_cast<std::int64_t>(normalized_to.z) - normalized_from.z));
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
        auto map = _player->getMap();
        map->addObject(_player);
        _player->relocateWithoutMoveHooks(map->getEntry());
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
