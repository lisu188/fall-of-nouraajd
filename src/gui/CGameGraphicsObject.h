#pragma once

#include "object/CGameObject.h"

class CGui;


class CGameGraphicsObject : public CGameObject {
V_META(CGameGraphicsObject, CGameObject, vstd::meta::empty())
    std::list<std::pair<std::function<bool(SDL_Event *)>, std::function<bool(SDL_Event *) >>> eventCallbackList;
public:
    virtual void render(std::shared_ptr<CGui> reneder, SDL_Rect *pos, int frameTime, std::string object);

    bool event(SDL_Event *event);

    void registerEventCallback(std::function<bool(SDL_Event *)> pred, std::function<bool(SDL_Event *)> func);
};