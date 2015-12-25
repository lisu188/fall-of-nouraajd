#pragma once

#include "core/CGlobal.h"

class CGameObject;

class CMap;

class CClickAction {
public:
    virtual void onClickAction(std::shared_ptr<CGameObject> object) = 0;
};

class CMouseHandler {
public:
    CMouseHandler();

    void handleClick(std::shared_ptr<CGameObject> object);
};
