#pragma once
#include "CController.h"

class CTargetController : public CController {
    Q_OBJECT
public:
    CTargetController ( std::shared_ptr<CMapObject> target );
    virtual std::shared_ptr<vstd::future<void, Coords> > control ( std::shared_ptr<CCreature> creature ) override;
private:
    std::shared_ptr<CMapObject> target;
};
GAME_PROPERTY ( CTargetController )
