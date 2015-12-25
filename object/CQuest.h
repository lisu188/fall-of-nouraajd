#pragma once

#include "CGameObject.h"

class CQuest : public CGameObject {
Q_OBJECT
public:
    CQuest();

    virtual bool isCompleted();

    virtual void onComplete();
};

GAME_PROPERTY (CQuest)
