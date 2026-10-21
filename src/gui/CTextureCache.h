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

#include <cstddef>

// TODO: generify all cache classes

class CTextureCache : public CGameObject {
    V_META(CTextureCache, CGameObject, vstd::meta::empty())
    std::unordered_map<std::string, fn::sdl::GuiTexturePtr> _textures;

  public:
    CTextureCache(std::shared_ptr<CGui> _gui);

    CTextureCache();

    ~CTextureCache();

    SDL_Texture *getTexture(std::string path);

    SDL_Texture *getTileTexture(std::string path, const SDL_Rect &target);

    std::size_t getTextureLoadCountForTesting() const { return textureLoadCount; }

    std::size_t getTileTextureBuildCountForTesting() const { return tileTextureBuildCount; }

    std::size_t getTileTextureEntryCountForTesting() const { return tileTextures.size(); }

  private:
    struct TileTexture {
        int width = 0;
        int height = 0;
        bool scaleSafe = false;
        fn::sdl::GuiTexturePtr texture;
    };

    fn::sdl::TexturePtr loadTexture(std::string path, int targetWidth = 0, int targetHeight = 0,
                                    bool *scaleSafe = nullptr);

    std::weak_ptr<CGui> _gui;
    std::unordered_map<std::string, TileTexture> tileTextures;
    std::size_t textureLoadCount = 0;
    std::size_t tileTextureBuildCount = 0;
};

class CTextureUtil {
  public:
    static fn::sdl::TexturePtr calculateAlpha(SDL_Renderer *renderer, fn::sdl::SurfacePtr surface, int targetWidth = 0,
                                              int targetHeight = 0, bool *scaleSafe = nullptr);

    static auto getPixelRgba(SDL_Surface *surface, int x, int y);

    static auto getPixelColor(SDL_Surface *surface, int x, int y);

    static void setPixelColor(SDL_Surface *surface, int x, int y, std::tuple<Uint8, Uint8, Uint8, Uint8> color);

    static std::unordered_set<std::pair<int, int>, vstd::pair_hash> calculateMask(SDL_Surface *pSurface);
};
