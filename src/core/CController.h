#pragma once

#include "object/CObject.h"
#include "core/CPathFinder.h"

class CController : public CGameObject {
V_META(CController, CGameObject, vstd::meta::empty())
public:
    virtual std::shared_ptr<vstd::future<void, Coords> > control(std::shared_ptr<CCreature> c);
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
       V_PROPERTY(CGroundController, std::string, ground_type, get_ground_type, set_ground_type))
public:
    virtual std::shared_ptr<vstd::future<void, Coords> > control(std::shared_ptr<CCreature> creature);

    std::string get_ground_type();

    void set_ground_type(std::string type);

private:
    std::string _ground_type;
};

class CRangeController : public CController {
V_META(CRangeController, CController,
       V_PROPERTY(CRangeController, std::shared_ptr<CMapObject>, target, get_target, set_target),
       V_PROPERTY(CRangeController, int, distance, get_distance, set_distance)
)

public:
    CRangeController();

    CRangeController(std::shared_ptr<CMapObject> target);

    virtual std::shared_ptr<vstd::future<void, Coords> > control(std::shared_ptr<CCreature> creature);

    std::shared_ptr<CMapObject> get_target();

    void set_target(std::shared_ptr<CMapObject> target);

    int get_distance();

    void set_distance(int distance);

private:
    int distance = 15;
    std::weak_ptr<CMapObject> target;
};