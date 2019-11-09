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
#include "CTextManager.h"
#include "core/CUtil.h"

SDL_Texture *CTextManager::getTexture(std::string text, int width) {
    auto anim = _textures.find(std::make_pair(text, width));
    if (anim == _textures.end()) {
        _textures[std::make_pair(text, width)] = this->loadTexture(text, width);
        return getTexture(text, width);
    }
    return _textures[std::make_pair(text, width)];
}

SDL_Texture *CTextManager::loadTexture(std::string text, int width) {
    SDL_Color textColor = {255, 255, 255, 0};
    SDL_Surface *surface = SDL_SAFE(TTF_RenderText_Blended_Wrapped(font, text.c_str(), textColor, width));
    auto _texture = SDL_SAFE(SDL_CreateTextureFromSurface(_gui.lock()->getRenderer(), surface));
    SDL_SAFE(SDL_FreeSurface(surface));
    return _texture;
}

CTextManager::CTextManager(std::shared_ptr<CGui> _gui) {
    SDL_SAFE(TTF_Init());
    font = SDL_SAFE(TTF_OpenFont("fonts/ampersand.ttf", 24));
    this->_gui = _gui;
}

CTextManager::~CTextManager() {
    for (auto texture:_textures) {
        SDL_SAFE(SDL_DestroyTexture(texture.second));
    }
    _textures.clear();
    SDL_SAFE(TTF_CloseFont(font));
}


void CTextManager::drawText(std::string text, int x, int y, int w) {
    if (text.length() != 0) {
        SDL_Rect actual;
        actual.x = x;
        actual.y = y;
        SDL_Texture *pTexture = getTexture(text, w);
        SDL_SAFE(SDL_QueryTexture(pTexture, NULL, NULL, &actual.w, &actual.h));
        SDL_SAFE(SDL_RenderCopy(_gui.lock()->getRenderer(), pTexture, NULL, &actual));
    }
}

void CTextManager::drawTextCentered(std::string text, int x, int y, int w, int h) {
    if (text.length() != 0) {
        SDL_Rect actual;
        SDL_Texture *pTexture = getTexture(text, w);
        SDL_SAFE(SDL_QueryTexture(pTexture, NULL, NULL, &actual.w, &actual.h));
        auto centered = CUtil::boxInBox(RECT(x, y, w, h), RECT(0, 0, actual.w, actual.h));
        SDL_SAFE(SDL_RenderCopy(_gui.lock()->getRenderer(), pTexture, NULL, centered.get()));
    }
}

void CTextManager::drawTextCentered(std::string text, std::shared_ptr<SDL_Rect> rect) {
    drawTextCentered(text, rect->x, rect->y, rect->w, rect->h);
}

void CTextManager::drawText(std::string text, std::shared_ptr<SDL_Rect> rect) {
    drawText(text, rect->x, rect->y, rect->w);
}
