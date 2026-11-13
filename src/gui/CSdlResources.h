/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026  Andrzej Lis

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

#include "core/CGlobal.h"

class CGui;

namespace fn::sdl {
template <typename T, auto Destroy>
    requires requires(T *resource) {
        { std::invoke(Destroy, resource) } -> std::same_as<void>;
    }
struct ResourceDeleter {
    void operator()(T *resource) const noexcept {
        if (resource) {
            std::invoke(Destroy, resource);
        }
    }
};

using SurfaceDeleter = ResourceDeleter<SDL_Surface, SDL_FreeSurface>;
using TextureDeleter = ResourceDeleter<SDL_Texture, SDL_DestroyTexture>;
using RendererDeleter = ResourceDeleter<SDL_Renderer, SDL_DestroyRenderer>;
using WindowDeleter = ResourceDeleter<SDL_Window, SDL_DestroyWindow>;
using FontDeleter = ResourceDeleter<TTF_Font, TTF_CloseFont>;

struct GuiTextureDeleter {
    std::weak_ptr<CGui> owner;

    void operator()(SDL_Texture *texture) const noexcept;
};

using SurfacePtr = std::unique_ptr<SDL_Surface, SurfaceDeleter>;
using TexturePtr = std::unique_ptr<SDL_Texture, TextureDeleter>;
using GuiTexturePtr = std::unique_ptr<SDL_Texture, GuiTextureDeleter>;
using RendererPtr = std::unique_ptr<SDL_Renderer, RendererDeleter>;
using WindowPtr = std::unique_ptr<SDL_Window, WindowDeleter>;
using FontPtr = std::unique_ptr<TTF_Font, FontDeleter>;
} // namespace fn::sdl
