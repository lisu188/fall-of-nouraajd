#pragma once

#include "object/CGameObject.h"
#include "core/CGlobal.h"
#include "gui/object/CGameGraphicsObject.h"
#include "gui/CTextureCache.h"

class CGui : public CGameObject {
V_META(CGui, CGameObject, vstd::meta::empty())
    SDL_Window *window = 0;
    SDL_Renderer *renderer = 0;
public:
    SDL_Renderer *getRenderer() const;

private:
    std::list<std::shared_ptr<CGameGraphicsObject>> gui_stack;
public:
    CGui();

    ~CGui();

    void addObject(std::shared_ptr<CGameGraphicsObject> object);

    void removeObject(std::shared_ptr<CGameGraphicsObject> object);

    void render(int i1);

    bool event(SDL_Event *event);

    std::shared_ptr<CTextureCache> getTextureCache();

    vstd::lazy<CTextureCache, CTextureCache> _textureCache;
};

template<typename T=void>
class CColor {
public:
    static SDL_Color *blue() {
        static SDL_Color blue = {0, 0, 255, 0};
        return &blue;
    }

    static SDL_Color *red() {
        static SDL_Color red = {255, 0, 0, 0};
        return &red;
    }

    static SDL_Color *yellow() {
        static SDL_Color yellow = {255, 255, 0, 0};
        return &yellow;
    }

    static SDL_Color *black() {
        static SDL_Color black = {0, 0, 0, 0};
        return &black;
    }
};

#define COLOR(x) x->r,x->g,x->b,x->a