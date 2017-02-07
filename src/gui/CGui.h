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

    void render();

    bool event(SDL_Event *event);

    std::shared_ptr<CAnimationHandler> getAnimationHandler();

    std::shared_ptr<CAnimationHandler> _animationHandler = std::make_shared<CAnimationHandler>();
};
