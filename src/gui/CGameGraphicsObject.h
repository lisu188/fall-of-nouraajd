#pragma once

#include "object/CGameObject.h"

class CGui;

class CGameGraphicsObject : public CGameObject {
V_META(CGameGraphicsObject, CGameObject, vstd::meta::empty())
public:
    virtual void render(std::shared_ptr<CGui> reneder, SDL_Rect *pos, int i1);

    virtual bool event(SDL_Event *event);
};