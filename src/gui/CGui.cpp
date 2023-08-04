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
#include "CGui.h"
#include "gui/CTextureCache.h"
#include "gui/CTextManager.h"

CGui::CGui() {
    SDL_SAFE(SDL_Init(SDL_INIT_VIDEO));
    SDL_SAFE(SDL_CreateWindowAndRenderer(width, height, SDL_WINDOW_OPENGL, &window, &renderer));
    //TODO: set icon
    //TODO: check render flags
}

CGui::~CGui() {
    SDL_SAFE(SDL_DestroyRenderer(renderer));
    SDL_SAFE(SDL_DestroyWindow(window));
}

void CGui::render(int i1) {
    SDL_SAFE(SDL_SetRenderDrawColor(renderer, BLACK));
    SDL_SAFE(SDL_RenderClear(renderer));
    CGameGraphicsObject::render(this->ptr<CGui>(), i1);
    SDL_SAFE(SDL_RenderPresent(renderer));
}

bool CGui::event(SDL_Event *event) {
    return CGameGraphicsObject::event(this->ptr<CGui>(), event);
}

SDL_Renderer *CGui::getRenderer() const {
    return renderer;
}

std::shared_ptr<CTextureCache> CGui::getTextureCache() {
    return _textureCache.get([this]() {
        return std::make_shared<CTextureCache>(this->ptr<CGui>());
    });
}

std::shared_ptr<CTextManager> CGui::getTextManager() {
    return _textManager.get([this]() {
        return std::make_shared<CTextManager>(this->ptr<CGui>());
    });
}

int CGui::getWidth() {
    return width;
}

void CGui::setWidth(int width) {
    CGui::width = width;
}

int CGui::getHeight() {
    return height;
}

void CGui::setHeight(int height) {
    CGui::height = height;
}

int CGui::getTileSize() {
    return tileSize;
}

void CGui::setTileSize(int tileSize) {
    CGui::tileSize = tileSize;
}

int CGui::getTileCountX() {
    return width / tileSize + 1;
}

int CGui::getTileCountY() {
    return height / tileSize + 1;
}