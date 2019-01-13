#pragma once


#include "core/CGame.h"
#include "object/CGameObject.h"
#include "core/CGlobal.h"
#include "gui/object/CGameGraphicsObject.h"

class CTextureCache;

class CTextManager;

class CGui : public CGameObject {
V_META(CGui, CGameObject,
       V_PROPERTY(CGui, int, height, getHeight, setHeight),
       V_PROPERTY(CGui, int, width, getWidth, setWidth),
       V_PROPERTY(CGui, int, tileSize, getTileSize, setTileSize))
    SDL_Window *window = 0;
    SDL_Renderer *renderer = 0;
public:
    SDL_Renderer *getRenderer() const;

private:
    std::list<std::shared_ptr<CGameGraphicsObject>> guiStack;
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

    std::shared_ptr<CTextManager> getTextManager();

    vstd::lazy<CTextureCache> _textureCache;

    vstd::lazy<CTextManager> _textManager;
};


#define BLUE 0, 0, 255, 0
#define RED 255, 0, 0, 0
#define YELLOW 255, 255, 0, 0
#define BLACK 0, 0, 0, 0

