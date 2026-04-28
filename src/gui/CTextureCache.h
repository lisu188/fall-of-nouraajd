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
#pragma once

#include "gui/CAnimation.h"
#include "gui/CGui.h"
#include "gui/CSdlResources.h"
#include "object/CGameObject.h"

// TODO: generify all cache classes

class CTextureCache : public CGameObject {
    V_META(CTextureCache, CGameObject, vstd::meta::empty())
    std::unordered_map<std::string, fn::sdl::TexturePtr> _textures;

  public:
    CTextureCache(std::shared_ptr<CGui> _gui);

    CTextureCache();

    ~CTextureCache();

    SDL_Texture *getTexture(std::string path);

  private:
    fn::sdl::TexturePtr loadTexture(std::string path);

    std::weak_ptr<CGui> _gui;
};

class CTextureUtil {
  public:
    static fn::sdl::TexturePtr calculateAlpha(SDL_Renderer *renderer, fn::sdl::SurfacePtr surface);

    static auto getPixelRgba(SDL_Surface *surface, int x, int y);

    static auto getPixelColor(SDL_Surface *surface, int x, int y);

    static void setPixelColor(SDL_Surface *surface, int x, int y, std::tuple<Uint8, Uint8, Uint8, Uint8> color);

    static std::unordered_set<std::pair<int, int>> calculateMask(SDL_Surface *pSurface);
};
