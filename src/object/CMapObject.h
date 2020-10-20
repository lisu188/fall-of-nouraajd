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
#pragma once

#include "core/CUtil.h"
#include "CGameObject.h"

class CGameEvent;

class CMap;

class CCreature;

class CMapObject : public CGameObject, public Creatable, public Turnable {
    friend class CObjectHandler;

V_META(CMapObject, CGameObject,
       V_PROPERTY(CMapObject, int, posx, getPosX, setPosX),
       V_PROPERTY(CMapObject, int, posy, getPosY, setPosY),
       V_PROPERTY(CMapObject, int, posz, getPosZ, setPosZ),
       V_PROPERTY(CMapObject, bool, canStep, getCanStep, setCanStep),
       V_PROPERTY(CMapObject, std::string, affiliation, getAffiliation, setAffiliation)
)

public:
    CMapObject();

    virtual ~CMapObject();

    void setPosX(int posx);

    void setPosY(int posy);

    void setPosZ(int posz);


    std::string getAffiliation();

    void setAffiliation(const std::string &affiliation);

    int getPosX() const;

    int getPosY() const;

    int getPosZ() const;

    virtual void onTurn(std::shared_ptr<CGameEvent>) override;

    virtual void onCreate(std::shared_ptr<CGameEvent>) override;

    virtual void onDestroy(std::shared_ptr<CGameEvent>) override;

    Coords getCoords();

    void setCoords(Coords coords);

    virtual void move(int x, int y, int z);

    void move(Coords coords);

    void moveTo(int x, int y, int z);

    void moveTo(Coords coords);

    bool isAffiliatedWith(std::shared_ptr<CMapObject> object);

    bool getCanStep();

    void setCanStep(bool step);

private:
    int posx = 0;
    int posy = 0;
    int posz = 0;
    bool canStep = true;
    std::string affiliation;
};


