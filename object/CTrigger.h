#pragma once
#include "CGameObject.h"

class CTrigger : public CGameObject {
    Q_OBJECT
public:
    CTrigger();
    virtual void trigger ( std::shared_ptr<CGameObject>,std::shared_ptr<CGameEvent> );
};
GAME_PROPERTY ( CTrigger )
