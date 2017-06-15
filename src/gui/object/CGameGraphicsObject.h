#pragma once

#include "object/CGameObject.h"

class CGui;


class CGameGraphicsObject : public CGameObject {
V_META(CGameGraphicsObject, CGameObject, vstd::meta::empty())
    std::list<std::pair<std::function<bool(std::shared_ptr<CGui>, SDL_Event *)>, std::function<bool(
            std::shared_ptr<CGui>, SDL_Event *) >>> eventCallbackList;
public:
    virtual void render(std::shared_ptr<CGui> reneder, SDL_Rect *pos, int frameTime, std::string object);

    virtual bool event(std::shared_ptr<CGui> gui, SDL_Event *event);

    void registerEventCallback(std::function<bool(std::shared_ptr<CGui>, SDL_Event *)> pred,
                               std::function<bool(std::shared_ptr<CGui>, SDL_Event *)> func);
};