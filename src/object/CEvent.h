#pragma once

#include "CMapObject.h"

class CEvent : public CMapObject, public Visitable {

V_META(CEvent, CMapObject,
       V_PROPERTY(CEvent, bool, enabled, isEnabled, setEnabled)
)

public:
    CEvent();

    bool isEnabled();

    void setEnabled(bool enabled);

    virtual void onEnter(std::shared_ptr<CGameEvent>) override;

    virtual void onLeave(std::shared_ptr<CGameEvent>) override;

private:
    bool enabled = true;
};

GAME_PROPERTY (CEvent)
