/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
#pragma once


#include "core/CGame.h"
#include "object/CGameObject.h"
#include "core/CGlobal.h"
#include "gui/object/CGameGraphicsObject.h"

class CTextureCache;

class CTextManager;

class CGui : public CGameGraphicsObject {
V_META(CGui, CGameGraphicsObject,
       V_PROPERTY(CGui, int, height, getHeight, setHeight),
       V_PROPERTY(CGui, int, width, getWidth, setWidth),
       V_PROPERTY(CGui, int, tileSize, getTileSize, setTileSize))
    SDL_Window *window = 0;
    SDL_Renderer *renderer = 0;
public:
    SDL_Renderer *getRenderer() const;

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

