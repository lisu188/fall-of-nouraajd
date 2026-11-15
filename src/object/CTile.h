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
#pragma once

#include "CMapObject.h"
#include "core/CGlobal.h"

#include <memory>
#include <optional>
#include <vector>

class CGame;

class CCreature;

class CTile : public CGameObject {
    friend class CMap;
    friend class CGameObject;
    friend class CRandomMapGenerator;

    V_META(CTile, CGameObject, V_PROPERTY(CTile, bool, canStep, canStep, setCanStep),
           V_PROPERTY(CTile, int, posx, getPosx, setPosx), V_PROPERTY(CTile, int, posy, getPosy, setPosy),
           V_PROPERTY(CTile, int, posz, getPosz, setPosz),
           V_PROPERTY(CTile, int, movementCost, getMovementCost, setMovementCost),
           V_PROPERTY(CTile, std::string, tileType, getTileType, setTileType))

  public:
    CTile();

    virtual ~CTile();

    virtual void onStep(std::shared_ptr<CCreature>);

    void move(int x, int y, int z);

    void moveTo(int x, int y, int z);

    Coords getCoords();

    bool canStep() const;

    void setCanStep(bool canStep);

    int getPosx() const;

    void setPosx(int value);

    int getPosy() const;

    void setPosy(int value);

    int getPosz() const;

    void setPosz(int value);

    int getMovementCost() const;

    void setMovementCost(int value);

    const std::string &getTileType() const;

    void setTileType(const std::string &tileType);

  private:
    std::string tileType;
    bool step = false;
    int movementCost = 1;
    int posx = 0, posy = 0, posz = 0;
    std::weak_ptr<CMap> terrainObserver;
    std::unique_ptr<std::vector<std::weak_ptr<CMap>>> additionalTerrainObservers;

    void setXYZ(int x, int y, int z);
    void addTerrainObserver(const std::shared_ptr<CMap> &map);
    void removeTerrainObserver(const CMap *map);
    void notifyTerrainChanged(std::optional<int> previousLevel = std::nullopt);
};
