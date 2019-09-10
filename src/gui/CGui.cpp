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
    //TODO: check render flags
}

CGui::~CGui() {
    SDL_SAFE(SDL_DestroyRenderer(renderer));
    SDL_SAFE(SDL_DestroyWindow(window));
}

void CGui::render(int frameTime) {
    SDL_SAFE(SDL_SetRenderDrawColor(renderer, BLACK));
    SDL_SAFE(SDL_RenderClear(renderer));
    for (std::shared_ptr<CGameGraphicsObject> object:guiStack) {
        object->render(this->ptr<CGui>(), RECT(0, 0, width, height), frameTime);
    }
    SDL_SAFE(SDL_RenderPresent(renderer));
}

bool CGui::event(SDL_Event *event) {
    for (std::shared_ptr<CGameGraphicsObject> object:guiStack | boost::adaptors::reversed) {
        if (object->event(this->ptr<CGui>(), event)) {
            return true;
        }
    }
    return false;
}

void CGui::addObject(std::shared_ptr<CGameGraphicsObject> object) {
    guiStack.push_back(object);
}

void CGui::removeObject(std::shared_ptr<CGameGraphicsObject> object) {
    guiStack.erase(
            std::remove_if(guiStack.begin(), guiStack.end(), [object](std::shared_ptr<CGameGraphicsObject> ob) {
                return ob.get() == object.get();
            }), guiStack.end());
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
    return width / tileSize;
}

int CGui::getTileCountY() {
    return height / tileSize;
}

CGuiStack CGui::getGuiStack() {
    CGuiStack stack;
    int i = 0;
    for (auto it:guiStack) {
        stack.insert(std::make_pair(vstd::str(i++), it));
    }
    return stack;
}

void CGui::setGuiStack(CGuiStack stack) {
    for (size_t i = 0; i < stack.size(); i++) {
        addObject(stack[vstd::str(i)]);
    }
}

