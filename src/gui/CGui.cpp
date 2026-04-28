/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025-2026  Andrzej Lis

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
#include "core/CUtil.h"
#include "gui/CTextManager.h"
#include "gui/CTextureCache.h"

CGui::CGui() {
    SDL_SAFE(SDL_Init(SDL_INIT_VIDEO));
    SDL_Window *rawWindow = nullptr;
    SDL_Renderer *rawRenderer = nullptr;
    SDL_SAFE(SDL_CreateWindowAndRenderer(width, height, 0, &rawWindow, &rawRenderer));
    window.reset(rawWindow);
    renderer.reset(rawRenderer);
    // TODO: set icon
    // TODO: check render flags
}

CGui::~CGui() = default;

void CGui::render(int i1) {
    CUtil::setRenderDrawColor(renderer.get(), CColors::Black);
    SDL_SAFE(SDL_RenderClear(renderer.get()));
    CGameGraphicsObject::render(this->ptr<CGui>(), i1);
    SDL_SAFE(SDL_RenderPresent(renderer.get()));
}

bool CGui::event(SDL_Event *event) { return CGameGraphicsObject::event(this->ptr<CGui>(), event); }

SDL_Renderer *CGui::getRenderer() const { return renderer.get(); }

std::shared_ptr<CTextureCache> CGui::getTextureCache() {
    return _textureCache.get([this]() { return std::make_shared<CTextureCache>(this->ptr<CGui>()); });
}

std::shared_ptr<CTextManager> CGui::getTextManager() {
    return _textManager.get([this]() { return std::make_shared<CTextManager>(this->ptr<CGui>()); });
}

int CGui::getWidth() { return width; }

void CGui::setWidth(int width) { CGui::width = width; }

int CGui::getHeight() { return height; }

void CGui::setHeight(int height) { CGui::height = height; }

int CGui::getTileSize() { return tileSize; }

void CGui::setTileSize(int tileSize) { CGui::tileSize = tileSize; }

int CGui::getTileCountX() { return width / tileSize + 1; }

int CGui::getTileCountY() { return height / tileSize + 1; }
