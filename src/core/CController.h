#pragma once

#include "object/CObject.h"
#include "core/CPathFinder.h"
#include "core/CDefines.h"

class CController : public CGameObject {
V_META(CController, CGameObject, vstd::meta::empty())
public:
    virtual std::shared_ptr<vstd::future<void, Coords> > control(std::shared_ptr<CCreature> c);
};

GAME_PROPERTY (CController)

class CTargetController : public CController {
V_META(CTargetController, CController, vstd::meta::empty())
public:
    CTargetController();

    CTargetController(std::shared_ptr<CMapObject> target);

    virtual std::shared_ptr<vstd::future<void, Coords> > control(std::shared_ptr<CCreature> creature) override;

private:
    std::shared_ptr<CMapObject> target;
};

GAME_PROPERTY (CTargetController)