/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025  Andrzej Lis

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

#include "object/CObject.h"
#include "core/CPathFinder.h"

class CGameFightPanel;

class CController : public CGameObject {
V_META(CController, CGameObject, vstd::meta::empty())
public:

    virtual std::shared_ptr<vstd::future<Coords, void>> control(std::shared_ptr<CCreature> c);
};

class CPlayerController : public CController {
V_META(CPlayerController, CController, vstd::meta::empty())

public:
    void setTarget(std::shared_ptr<CPlayer> player, Coords target);

    virtual std::shared_ptr<vstd::future<Coords, void>> control(std::shared_ptr<CCreature> c);

    std::pair<bool, Coords::Direction> isOnPath(std::shared_ptr<CPlayer> player, Coords coords);

    bool isCompleted(std::shared_ptr<CPlayer> player);

private:
    std::shared_ptr<Coords> target;
    std::unordered_map<int, Coords> path;
    int currentStep = 0;

    std::vector<Coords> calculatePath(std::shared_ptr<CPlayer> ptr);
};

class CFightController : public CGameObject {
V_META(CFightController, CGameObject, vstd::meta::empty())
public:
    virtual bool control(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent);

    virtual void start(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent);

    virtual void end(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent);
};

class CMonsterFightController : public CFightController {
V_META(CMonsterFightController, CFightController, vstd::meta::empty())
public:
    bool control(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) override;

private:
    std::shared_ptr<CInteraction> selectInteraction(std::shared_ptr<CCreature> cr);

    std::shared_ptr<CItem> getLeastPowerfulItemWithTag(std::shared_ptr<CCreature> cr, std::string tag);
};

class CPlayerFightController : public CFightController {
V_META(CPlayerFightController, CFightController, vstd::meta::empty())
public:
    bool control(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) override;

    void start(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) override;

    void end(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) override;

private:
    std::shared_ptr<CGameFightPanel> fightPanel;
};


//should accept script
class CTargetController : public CController {
V_META(CTargetController, CController,
       V_PROPERTY(CTargetController, std::string, target, getTarget, setTarget))
public:
    CTargetController();

    std::shared_ptr<vstd::future<Coords, void>> control(std::shared_ptr<CCreature> creature) override;

    std::string getTarget();

    void setTarget(std::string);

private:
    std::string target;
};

class CRandomController : public CController {
V_META(CRandomController, CController, vstd::meta::empty())
public:
    std::shared_ptr<vstd::future<Coords, void>> control(std::shared_ptr<CCreature> creature) override;
};

class CNpcRandomController : public CController {
V_META(CNpcRandomController, CController, vstd::meta::empty())
public:
    std::shared_ptr<vstd::future<Coords, void>> control(std::shared_ptr<CCreature> creature) override;

private:
    std::vector<Coords> path;
    int currentStep = 0;
};

class CGroundController : public CController {
V_META(CGroundController, CController,
       V_PROPERTY(CGroundController, std::string, tileType, getTileType, setTileType))
public:
    std::shared_ptr<vstd::future<Coords, void>> control(std::shared_ptr<CCreature> creature) override;

    std::string getTileType();

    void setTileType(std::string type);

private:
    std::string _tileType;
};

class CRangeController : public CController {
V_META(CRangeController, CController,
       V_PROPERTY(CRangeController, std::string, target, getTarget, setTarget),
       V_PROPERTY(CRangeController, int, distance, getDistance, setDistance)
)

public:
    CRangeController();

    std::shared_ptr<vstd::future<Coords, void>> control(std::shared_ptr<CCreature> creature) override;

    std::string getTarget();

    void setTarget(std::string target);

    int getDistance();

    void setDistance(int distance);

private:
    int distance = 15;
    std::string target;
};