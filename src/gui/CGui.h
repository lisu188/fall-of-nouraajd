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
    int getWidth();

    void setWidth(int width);

    int getHeight();

    void setHeight(int height);

    int getTileSize();

    void setTileSize(int tileSize);

    int getTileCountX();

    int getTileCountY();

private:
    int height = 1080;
    int tileSize = 50;
    int width = 1920;
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


#define BLUE 0, 0, 255, 0
#define RED 255, 0, 0, 0
#define YELLOW 255, 255, 0, 0
#define BLACK 0, 0, 0, 0

