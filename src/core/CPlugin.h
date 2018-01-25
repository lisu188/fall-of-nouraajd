#pragma once

#include "object/CGameObject.h"
#include "CGlobal.h"
#include "core/CProvider.h"

class CGame;

class CMap;

class CPlugin : public CGameObject {
V_META(CPlugin, CGameObject, vstd::meta::empty())
public:
    virtual void load(std::shared_ptr<CGame> game);
};

