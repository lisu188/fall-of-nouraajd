#pragma once

#include "core/CDefines.h"
#include "CController.h"

class CTargetController : public CController {

public:
    CTargetController ( std::shared_ptr<CMapObject> target );

    virtual std::shared_ptr<vstd::future<void, Coords> > control ( std::shared_ptr<CCreature> creature ) override;

private:
    std::shared_ptr<CMapObject> target;
};

GAME_PROPERTY ( CTargetController )
