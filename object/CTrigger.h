#pragma once
#include "CGameObject.h"

class CTrigger : public CGameObject {
    Q_OBJECT
public:
    CTrigger();
    virtual void trigger ( CGameObject *,CGameEvent * );
};

