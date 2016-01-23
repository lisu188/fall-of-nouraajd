#pragma once

#include "CGameObject.h"

class CQuest : public CGameObject {

public:
    CQuest();

    virtual bool isCompleted();

    virtual void onComplete();
};


