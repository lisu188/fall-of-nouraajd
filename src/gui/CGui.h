#pragma once

#include "object/CGameObject.h"
#include "core/CGlobal.h"
#include "gui/CGameGraphicsObject.h"
#include "gui/CAnimationHandler.h"

class CGui : public CGameObject {
    SDL_Window *window = 0;
    SDL_Renderer *renderer = 0;
public:
    SDL_Renderer *getRenderer() const;

private:

    //TODO: make linked hash set
    std::list<std::shared_ptr<CGameGraphicsObject>> gui_stack;
public:
    CGui();

    ~CGui();

    void addObject(std::shared_ptr<CGameGraphicsObject> object);

    void removeObject(std::shared_ptr<CGameGraphicsObject> object);

    void render(int i1);

    bool event(SDL_Event *event);

    std::shared_ptr<CAnimationHandler> getAnimationHandler();

    vstd::lazy<CAnimationHandler> _animationHandler;
};
