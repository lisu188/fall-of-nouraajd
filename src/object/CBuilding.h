#pragma once

#include"CMapObject.h"

class CBuilding : public CMapObject, public Visitable {

V_META(CBuilding, CMapObject,
       V_PROPERTY(CBuilding, bool, enabled, isEnabled, setEnabled)
)

public:
    CBuilding();

    virtual ~CBuilding();

    bool isEnabled();

    void setEnabled(bool enabled);

    virtual void onEnter(std::shared_ptr<CGameEvent>) override;

    virtual void onLeave(std::shared_ptr<CGameEvent>) override;

protected:
    bool enabled = true;
};

GAME_PROPERTY (CBuilding)
