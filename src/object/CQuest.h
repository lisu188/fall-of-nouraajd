#pragma once

#include "CGameObject.h"

class CQuest : public CGameObject {
V_META(CQuest, CGameObject, vstd::meta::empty())
public:
    CQuest();

    virtual bool isCompleted();

    virtual void onComplete();
};


