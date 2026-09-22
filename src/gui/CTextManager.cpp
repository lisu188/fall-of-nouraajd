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
#include "core/CProvider.h"
#include "core/CUtil.h"

#include <algorithm>
#include <cmath>

namespace {
constexpr std::size_t MAX_TEXT_TEXTURES = 512;
constexpr std::size_t MAX_RENDER_TEXT_BYTES = 4096;
constexpr int MAX_TEXT_WRAP_WIDTH = 8192;

std::string boundedText(std::string text) {
    if (text.size() > MAX_RENDER_TEXT_BYTES) {
        auto size = MAX_RENDER_TEXT_BYTES;
        while (size > 0 && (static_cast<unsigned char>(text[size]) & 0xc0) == 0x80)
            --size;
        text.resize(size);
    }
    return text;
}

int boundedWidth(int width) { return std::clamp(width, 0, MAX_TEXT_WRAP_WIDTH); }
} // namespace

SDL_Texture *CTextManager::getTexture(const std::string &text, int width, const std::string &role, SDL_Color color) {
    if (auto gui = _gui.lock(); gui && gui->isHighContrast())
        color = {255, 255, 255, 255};
    const auto normalizedRole =
        role == "title" || role == "heading" || role == "dialogue" || role == "small" ? role : "body";
    const int size = getFontSize(normalizedRole);
    const Uint32 packedColor = (Uint32(color.r) << 24) | (Uint32(color.g) << 16) | (Uint32(color.b) << 8) | color.a;
    auto key = std::make_tuple(boundedText(text), boundedWidth(width), normalizedRole, size, packedColor);
    auto texture = _textures.find(key);
    if (texture == _textures.end()) {
        if (_textures.size() >= MAX_TEXT_TEXTURES) {
            _textures.clear();
        }
        auto [inserted, _] =
            _textures.emplace(key, loadTexture(std::get<0>(key), std::get<1>(key), normalizedRole, size, color));
        return inserted->second.get();
    }
    return texture->second.get();
}

fn::sdl::TexturePtr CTextManager::loadTexture(const std::string &text, int width, const std::string &role, int size,
                                              SDL_Color color) {
    ++textureLoads;
    auto gui = _gui.lock();
    auto font = getFont(role, size);
    if (!font || !gui || !gui->getRenderer()) {
        return nullptr;
    }
    // in some sdl versions blended wrapped automatically treats 0 as not wrapper,
    // other versions fail on width=0
    auto surface = fn::sdl::SurfacePtr(SDL_SAFE(width ? TTF_RenderUTF8_Blended_Wrapped(font, text.c_str(), color, width)
                                                      : TTF_RenderUTF8_Blended(font, text.c_str(), color)));
    if (!surface) {
        return nullptr;
    }
    return fn::sdl::TexturePtr(SDL_SAFE(SDL_CreateTextureFromSurface(gui->getRenderer(), surface.get())));
}

CTextManager::CTextManager(const std::shared_ptr<CGui> &_gui) {
    SDL_SAFE(TTF_Init());
    this->_gui = _gui;
}

TTF_Font *CTextManager::getFont(const std::string &role, int size) {
    const std::string family =
        role == "title" || role == "heading" ? "SourceSerif4-Semibold.ttf" : "SourceSans3-Regular.ttf";
    auto key = std::make_pair(family, size);
    if (auto it = fonts.find(key); it != fonts.end())
        return it->second.get();
    // A bounded font cache also bounds native glyph caches after repeated scale changes.
    if (fonts.size() >= 24)
        fonts.clear();
    auto gui = _gui.lock();
    auto game = gui ? gui->getGame() : nullptr;
    auto resourcesProvider = game ? game->getResourcesProvider() : CResourcesProvider::getInstance();
    auto resolved = resourcesProvider->getPath("fonts/" + family);
    if (resolved.empty())
        resolved = resourcesProvider->getPath("fonts/ampersand.ttf");
    if (resolved.empty())
        return nullptr;
    auto [it, _] = fonts.emplace(key, fn::sdl::FontPtr(TTF_OpenFont(resolved.c_str(), size)));
    return it->second.get();
}

int CTextManager::getFontSize(const std::string &role) const {
    const int base = role == "title"      ? 36
                     : role == "heading"  ? 32
                     : role == "dialogue" ? 28
                     : role == "small"    ? 22
                                          : 24;
    auto gui = _gui.lock();
    return std::clamp(static_cast<int>(std::lround(base * (gui ? gui->getTextScale() : 1.0))), 18, 144);
}

CTextManager::~CTextManager() {
    _textures.clear();
    fonts.clear();
}

void CTextManager::clearCache() {
    _textures.clear();
    fonts.clear();
}
std::size_t CTextManager::getCachedTextureCount() const { return _textures.size(); }
std::size_t CTextManager::getCachedFontCount() const { return fonts.size(); }

std::pair<int, int> CTextManager::measureText(const std::string &text, int width, const std::string &role) {
    int w = 0, h = 0;
    if (auto texture = getTexture(text, width, role))
        SDL_QueryTexture(texture, nullptr, nullptr, &w, &h);
    return {w, h};
}

void CTextManager::drawTextStyled(const std::string &text, const std::shared_ptr<SDL_Rect> &rect,
                                  const std::string &role, SDL_Color color, bool centered, int offsetY) {
    auto gui = _gui.lock();
    if (!gui || !rect || text.empty() || rect->w <= 0 || rect->h <= 0)
        return;
    auto texture = getTexture(text, rect->w, role, color);
    if (!texture)
        return;
    SDL_Rect target{rect->x, rect->y + offsetY, 0, 0};
    SDL_QueryTexture(texture, nullptr, nullptr, &target.w, &target.h);
    if (centered) {
        target.x += std::max(0, (rect->w - target.w) / 2);
        target.y += std::max(0, (rect->h - target.h) / 2);
    }
    gui->getRenderContext().copy(texture, nullptr, &target, rect.get());
}

int CTextManager::countLines(const std::string &text, int w) {
    SDL_Rect wrapped;
    SDL_Texture *wrappedTexture = getTexture(text, w);
    if (!wrappedTexture) {
        return 1;
    }
    SDL_SAFE(SDL_QueryTexture(wrappedTexture, nullptr, nullptr, &wrapped.w, &wrapped.h));
    SDL_Rect notWrapped;
    SDL_Texture *notWrappedTexture = getTexture(text);
    if (!notWrappedTexture) {
        return 1;
    }
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
        if (!pTexture || !_gui.lock()) {
            return;
        }
        SDL_SAFE(SDL_QueryTexture(pTexture, nullptr, nullptr, &actual.w, &actual.h));
        _gui.lock()->getRenderContext().copy(pTexture, nullptr, &actual);
    }
}

void CTextManager::drawTextCentered(const std::string &text, int x, int y, int w, int h) {
    if (text.length() != 0) {
        SDL_Rect actual;
        SDL_Texture *pTexture = getTexture(text, w);
        if (!pTexture || !_gui.lock()) {
            return;
        }
        SDL_SAFE(SDL_QueryTexture(pTexture, nullptr, nullptr, &actual.w, &actual.h));
        auto centered = CUtil::boxInBox(CUtil::rect(x, y, w, h), CUtil::rect(0, 0, actual.w, actual.h));
        SDL_Rect clip = {x, y, std::max(0, w), std::max(0, h)};
        _gui.lock()->getRenderContext().copy(pTexture, nullptr, centered.get(), &clip);
    }
}

void CTextManager::drawTextCentered(const std::string &text, const std::shared_ptr<SDL_Rect> &rect) {
    drawTextCentered(text, rect->x, rect->y, rect->w, rect->h);
}

void CTextManager::drawText(const std::string &text, const std::shared_ptr<SDL_Rect> &rect) {
    drawTextScrolled(text, rect, 0);
}

void CTextManager::drawTextScrolled(const std::string &text, const std::shared_ptr<SDL_Rect> &rect, int offsetY) {
    if (!rect || !_gui.lock()) {
        return;
    }
    SDL_Rect clip = {rect->x, rect->y, std::max(0, rect->w), std::max(0, rect->h)};
    if (text.length() != 0) {
        SDL_Rect actual;
        actual.x = rect->x;
        actual.y = rect->y + offsetY;
        SDL_Texture *pTexture = getTexture(text, rect->w);
        if (!pTexture) {
            return;
        }
        SDL_SAFE(SDL_QueryTexture(pTexture, nullptr, nullptr, &actual.w, &actual.h));
        _gui.lock()->getRenderContext().copy(pTexture, nullptr, &actual, &clip);
    }
}

std::pair<int, int> CTextManager::getWrappedTextureSize(const std::string &text, int width) {
    int w = 0, h = 0;
    if (auto texture = getTexture(text, width)) {
        SDL_SAFE(SDL_QueryTexture(texture, nullptr, nullptr, &w, &h));
    }
    return {w, h};
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
        if (!pTexture) {
            return std::make_pair(0, 0);
        }
        SDL_SAFE(SDL_QueryTexture(pTexture, nullptr, nullptr, &w, &h));
    }
    return std::make_pair(w, h);
}
