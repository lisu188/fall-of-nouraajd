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
#include "CTextManager.h"
#include "core/CUtil.h"

SDL_Texture *CTextManager::getTexture(const std::string &text, int width) {
    auto key = std::make_pair(text, width);
    auto texture = _textures.find(key);
    if (texture == _textures.end()) {
        auto [inserted, _] = _textures.emplace(std::move(key), this->loadTexture(text, width));
        return inserted->second.get();
    }
    return texture->second.get();
}

fn::sdl::TexturePtr CTextManager::loadTexture(std::string text, int width) {
    SDL_Color textColor = {255, 255, 255, 0};
    // in some sdl versions blended wrapped automatically treats 0 as not wrapper,
    // other versions fail on width=0
    auto surface =
        fn::sdl::SurfacePtr(SDL_SAFE(width ? TTF_RenderText_Blended_Wrapped(font.get(), text.c_str(), textColor, width)
                                           : TTF_RenderText_Blended(font.get(), text.c_str(), textColor)));
    if (!surface) {
        return nullptr;
    }
    return fn::sdl::TexturePtr(SDL_SAFE(SDL_CreateTextureFromSurface(_gui.lock()->getRenderer(), surface.get())));
}

CTextManager::CTextManager(const std::shared_ptr<CGui> &_gui) {
    SDL_SAFE(TTF_Init());
    font.reset(SDL_SAFE(TTF_OpenFont("fonts/ampersand.ttf", 24)));
    this->_gui = _gui;
}

CTextManager::~CTextManager() {
    _textures.clear();
    font.reset();
}

int CTextManager::countLines(const std::string &text, int w) {
    SDL_Rect wrapped;
    SDL_Texture *wrappedTexture = getTexture(text, w);
    SDL_SAFE(SDL_QueryTexture(wrappedTexture, nullptr, nullptr, &wrapped.w, &wrapped.h));
    SDL_Rect notWrapped;
    SDL_Texture *notWrappedTexture = getTexture(text);
    SDL_SAFE(SDL_QueryTexture(notWrappedTexture, nullptr, nullptr, &notWrapped.w, &notWrapped.h));
    if (wrapped.h <= 0 || notWrapped.h <= 0) {
        return 1;
    }
    int lines = wrapped.h / notWrapped.h;
    return lines > 0 ? lines : 1;
}

void CTextManager::drawText(const std::string &text, int x, int y, int w) {
    if (text.length() != 0) {
        SDL_Rect actual;
        actual.x = x;
        actual.y = y;
        SDL_Texture *pTexture = getTexture(text, w);
        SDL_SAFE(SDL_QueryTexture(pTexture, nullptr, nullptr, &actual.w, &actual.h));
        SDL_SAFE(SDL_RenderCopy(_gui.lock()->getRenderer(), pTexture, nullptr, &actual));
    }
}

void CTextManager::drawTextCentered(const std::string &text, int x, int y, int w, int h) {
    if (text.length() != 0) {
        SDL_Rect actual;
        SDL_Texture *pTexture = getTexture(text, w);
        SDL_SAFE(SDL_QueryTexture(pTexture, nullptr, nullptr, &actual.w, &actual.h));
        auto centered = CUtil::boxInBox(CUtil::rect(x, y, w, h), CUtil::rect(0, 0, actual.w, actual.h));
        SDL_SAFE(SDL_RenderCopy(_gui.lock()->getRenderer(), pTexture, nullptr, centered.get()));
    }
}

void CTextManager::drawTextCentered(const std::string &text, const std::shared_ptr<SDL_Rect> &rect) {
    drawTextCentered(text, rect->x, rect->y, rect->w, rect->h);
}

void CTextManager::drawText(const std::string &text, const std::shared_ptr<SDL_Rect> &rect) {
    drawText(text, rect->x, rect->y, rect->w);
}

std::pair<int, int> CTextManager::getTextureSize(std::string text) {
    int w = 0, h = 0;
    if (vstd::ctn(text, '\n')) {
        for (const auto &line : vstd::split(text, '\n')) {
            auto lineSize = getTextureSize(line);
            if (lineSize.first > w) {
                w = lineSize.first;
            }
            h += lineSize.second;
        }
    } else {
        SDL_Texture *pTexture = getTexture(text);
        SDL_SAFE(SDL_QueryTexture(pTexture, nullptr, nullptr, &w, &h));
    }
    return std::make_pair(w, h);
}
