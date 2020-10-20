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

#include "object/CObject.h"
#include "core/CPathFinder.h"

class CGameFightPanel;

class CController : public CGameObject {
V_META(CController, CGameObject, vstd::meta::empty())
public:
    virtual std::shared_ptr<vstd::future<void, Coords> > control(std::shared_ptr<CCreature> c);
};

class CPlayerController : public CController {
V_META(CPlayerController, CController, vstd::meta::empty())

public:
    void setTarget(Coords coords);

    Coords getTarget();

    virtual std::shared_ptr<vstd::future<void, Coords>> control(std::shared_ptr<CCreature> c);

    bool isCompleted();

private:
    std::shared_ptr<vstd::future<Coords, void>> getPathfinder(std::shared_ptr<CCreature> c);

    Coords target;

    bool completed = false;
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
    virtual bool control(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) override;

private:
    std::shared_ptr<CInteraction> selectInteraction(std::shared_ptr<CCreature> cr);

    std::shared_ptr<CItem> getLeastPowerfulItemWithTag(std::shared_ptr<CCreature> cr, std::string tag);
};

class CPlayerFightController : public CFightController {
V_META(CPlayerFightController, CFightController, vstd::meta::empty())
public:
    virtual bool control(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) override;

    virtual void start(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) override;

    virtual void end(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent) override;

private:
    std::shared_ptr<CGameFightPanel> fightPanel;
};


//should accept script
class CTargetController : public CController {
V_META(CTargetController, CController,
       V_PROPERTY(CTargetController, std::string, target, getTarget, setTarget))
public:
    CTargetController();

    virtual std::shared_ptr<vstd::future<void, Coords> > control(std::shared_ptr<CCreature> creature) override;

    std::string getTarget();

    void setTarget(std::string);

private:
    std::string target;
};

class CRandomController : public CController {
V_META(CRandomController, CController, vstd::meta::empty())
public:
    virtual std::shared_ptr<vstd::future<void, Coords> > control(std::shared_ptr<CCreature> creature);
};

class CGroundController : public CController {
V_META(CGroundController, CController,
       V_PROPERTY(CGroundController, std::string, tileType, getTileType, setTileType))
public:
    virtual std::shared_ptr<vstd::future<void, Coords> > control(std::shared_ptr<CCreature> creature);

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

    virtual std::shared_ptr<vstd::future<void, Coords> > control(std::shared_ptr<CCreature> creature);

    std::string getTarget();

    void setTarget(std::string target);

    int getDistance();

    void setDistance(int distance);

private:
    int distance = 15;
    std::string target;
};