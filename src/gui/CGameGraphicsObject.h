#pragma once

#include "object/CGameObject.h"

class CGameGraphicsObject : public CGameObject {
V_META(CGameGraphicsObject, CGameObject, vstd::meta::empty())
public:
    virtual void render(SDL_Renderer *reneder);

    virtual bool event(SDL_Event *event);
};