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

namespace fn::sdl {
struct SurfaceDeleter {
    void operator()(SDL_Surface *surface) const noexcept {
        if (surface) {
            SDL_FreeSurface(surface);
        }
    }
};

struct TextureDeleter {
    void operator()(SDL_Texture *texture) const noexcept {
        if (texture) {
            SDL_DestroyTexture(texture);
        }
    }
};

struct RendererDeleter {
    void operator()(SDL_Renderer *renderer) const noexcept {
        if (renderer) {
            SDL_DestroyRenderer(renderer);
        }
    }
};

struct WindowDeleter {
    void operator()(SDL_Window *window) const noexcept {
        if (window) {
            SDL_DestroyWindow(window);
        }
    }
};

struct FontDeleter {
    void operator()(TTF_Font *font) const noexcept {
        if (font) {
            TTF_CloseFont(font);
        }
    }
};

using SurfacePtr = std::unique_ptr<SDL_Surface, SurfaceDeleter>;
using TexturePtr = std::unique_ptr<SDL_Texture, TextureDeleter>;
using RendererPtr = std::unique_ptr<SDL_Renderer, RendererDeleter>;
using WindowPtr = std::unique_ptr<SDL_Window, WindowDeleter>;
using FontPtr = std::unique_ptr<TTF_Font, FontDeleter>;
} // namespace fn::sdl
