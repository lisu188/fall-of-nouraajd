#pragma once

#include "object/CObject.h"
#include "core/CPathFinder.h"

class CController : public CGameObject {
V_META(CController, CGameObject, vstd::meta::empty())
public:
    virtual std::shared_ptr<vstd::future<void, Coords> > control(std::shared_ptr<CCreature> c);
};

class CFightController : public CGameObject {
V_META(CFightController, CGameObject, vstd::meta::empty())
public:
    virtual bool control(std::shared_ptr<CCreature> me, std::shared_ptr<CCreature> opponent);

private:
    std::shared_ptr<CInteraction> selectInteraction(std::shared_ptr<CCreature> cr);

    std::shared_ptr<CItem> getLeastPowerfulItemWithTag(std::shared_ptr<CCreature> cr, std::string tag);
};

class CTargetController : public CController {
V_META(CTargetController, CController,
       V_PROPERTY(CTargetController, std::shared_ptr<CMapObject>, target, get_target, set_target))
public:
    CTargetController();

    CTargetController(std::shared_ptr<CMapObject> target);

    virtual std::shared_ptr<vstd::future<void, Coords> > control(std::shared_ptr<CCreature> creature) override;

    std::shared_ptr<CMapObject> get_target();

    void set_target(std::shared_ptr<CMapObject> target);

private:
    std::shared_ptr<CMapObject> target;
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