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
#include "CTile.h"
#include "CCreature.h"
#include "core/CGame.h"
#include "core/CMap.h"
#include "core/CPythonOverrides.h"

#include <algorithm>

CTile::CTile() {}

CTile::~CTile() {}

void CTile::move(int x, int y, int z) {
    if (auto map = getMap()) {
        Coords target = map->normalizeCoords(Coords(posx + x, posy + y, posz + z));
        map->moveTile(this->ptr<CTile>(), target.x, target.y, target.z);
    }
}

void CTile::moveTo(int x, int y, int z) { move(x - posx, y - posy, z - posz); }

Coords CTile::getCoords() { return Coords(posx, posy, posz); }

void CTile::onStep(std::shared_ptr<CCreature> creature) {
    pybind11::gil_scoped_acquire gil;
    if (auto override = CPythonOverrides::find_override(this, "onStep"); !override.is_none()) {
        PY_SAFE(override(creature); return;)
    }
}

bool CTile::canStep() const { return step; }

void CTile::setCanStep(bool canStep) {
    auto map = getMap();
    std::unique_lock<std::recursive_mutex> lock;
    if (map)
        lock = std::unique_lock(map->getNavigationMutex());
    if (step == canStep)
        return;
    step = canStep;
    if (map && map->hasRegisteredTile(this))
        map->navigationCellChanged(getCoords());
}

int CTile::getPosx() const { return posx; }

void CTile::setPosx(int value) {
    auto map = getMap();
    if (map && map->hasRegisteredTile(this)) {
        map->moveTile(ptr<CTile>(), value, posy, posz);
        return;
    }
    setXYZ(value, posy, posz);
}

int CTile::getPosy() const { return posy; }

void CTile::setPosy(int value) {
    auto map = getMap();
    if (map && map->hasRegisteredTile(this)) {
        map->moveTile(ptr<CTile>(), posx, value, posz);
        return;
    }
    setXYZ(posx, value, posz);
}

int CTile::getPosz() const { return posz; }

void CTile::setPosz(int value) {
    auto map = getMap();
    if (map && map->hasRegisteredTile(this)) {
        map->moveTile(ptr<CTile>(), posx, posy, value);
        return;
    }
    setXYZ(posx, posy, value);
}

int CTile::getMovementCost() const { return std::max(1, movementCost); }

void CTile::setMovementCost(int value) {
    auto map = getMap();
    std::unique_lock<std::recursive_mutex> lock;
    if (map)
        lock = std::unique_lock(map->getNavigationMutex());
    value = std::max(1, value);
    if (movementCost == value)
        return;
    movementCost = value;
    if (map && map->hasRegisteredTile(this))
        map->navigationCellChanged(getCoords());
}

void CTile::setXYZ(int x, int y, int z) {
    if (posx == x && posy == y && posz == z)
        return;
    const auto previousLevel = posz;
    posx = x;
    posy = y;
    posz = z;
    notifyTerrainChanged(previousLevel);
}

const std::string &CTile::getTileType() const { return tileType; }

void CTile::setTileType(const std::string &tileType) {
    if (CTile::tileType == tileType)
        return;
    CTile::tileType = tileType;
    notifyTerrainChanged();
}

void CTile::addTerrainObserver(const std::shared_ptr<CMap> &map) {
    if (!map)
        return;
    removeTerrainObserver(nullptr);
    if (terrainObserver.lock() == map)
        return;
    if (terrainObserver.expired()) {
        terrainObserver = map;
        return;
    }
    if (!additionalTerrainObservers)
        additionalTerrainObservers = std::make_unique<std::vector<std::weak_ptr<CMap>>>();
    if (std::ranges::none_of(*additionalTerrainObservers, [&map](const auto &entry) { return entry.lock() == map; }))
        additionalTerrainObservers->emplace_back(map);
}

void CTile::removeTerrainObserver(const CMap *map) {
    if (const auto owner = terrainObserver.lock(); !owner || owner.get() == map)
        terrainObserver.reset();
    if (!additionalTerrainObservers)
        return;
    std::erase_if(*additionalTerrainObservers, [map](const auto &entry) {
        const auto owner = entry.lock();
        return !owner || owner.get() == map;
    });
    if (terrainObserver.expired() && !additionalTerrainObservers->empty()) {
        terrainObserver = additionalTerrainObservers->back();
        additionalTerrainObservers->pop_back();
    }
    if (additionalTerrainObservers->empty())
        additionalTerrainObservers.reset();
}

void CTile::notifyTerrainChanged(std::optional<int> previousLevel) {
    removeTerrainObserver(nullptr);
    const auto notify = [this, previousLevel](const std::weak_ptr<CMap> &observer) {
        if (auto map = observer.lock()) {
            map->terrainChanged(posz);
            if (previousLevel && *previousLevel != posz)
                map->terrainChanged(*previousLevel);
        }
    };
    notify(terrainObserver);
    if (additionalTerrainObservers)
        for (const auto &observer : *additionalTerrainObservers)
            notify(observer);
}
