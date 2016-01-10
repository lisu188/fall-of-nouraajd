#pragma once

#include "CGameObject.h"

class CTrigger : public CGameObject {

public:
    CTrigger();

    virtual void trigger(std::shared_ptr<CGameObject>, std::shared_ptr<CGameEvent>);
};

GAME_PROPERTY (CTrigger)
