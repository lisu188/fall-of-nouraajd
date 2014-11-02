#pragma once
#include "CGameObject.h"

class CTrigger : public CGameObject {
public:
	CTrigger();
	virtual void trigger ( CGameObject *,CGameEvent * );
};

