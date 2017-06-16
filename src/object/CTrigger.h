#pragma once

#include "CGameObject.h"

class CTrigger : public CGameObject {
V_META(CTrigger, CGameObject, vstd::meta::empty())
public:
    CTrigger();

    virtual void trigger(std::shared_ptr<CGameObject>, std::shared_ptr<CGameEvent>);
};


