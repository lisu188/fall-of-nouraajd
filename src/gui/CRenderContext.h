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

class CRenderContext {
  public:
    struct RenderStats {
        std::size_t attemptedCopies = 0;
        std::size_t successfulCopies = 0;
        std::size_t failedCopies = 0;
        std::size_t skippedCopies = 0;
    };

    explicit CRenderContext(SDL_Renderer *renderer = nullptr);

    void setRenderer(SDL_Renderer *renderer);

    SDL_Renderer *getRenderer() const;

    bool copy(SDL_Texture *texture, const SDL_Rect *sourceRect, const SDL_Rect *targetRect,
              const SDL_Rect *clipRect = nullptr);

    bool copy(SDL_Texture *texture, const SDL_Rect *sourceRect, const SDL_Rect &targetRect,
              const SDL_Rect *clipRect = nullptr);

    bool copyEx(SDL_Texture *texture, const SDL_Rect *sourceRect, const SDL_Rect *targetRect, double angle,
                const SDL_Point *center, SDL_RendererFlip flip, const SDL_Rect *clipRect = nullptr);

    bool copyEx(SDL_Texture *texture, const SDL_Rect *sourceRect, const SDL_Rect &targetRect, double angle,
                const SDL_Point *center, SDL_RendererFlip flip, const SDL_Rect *clipRect = nullptr);

    const RenderStats &getStats() const;

    void resetStats();

    static SDL_Rect normalizeTargetRect(const SDL_Rect &rect);

  private:
    bool prepareCopy(SDL_Texture *texture, const SDL_Rect *targetRect, SDL_Rect &normalizedTarget,
                     const char *operation);

    bool finishCopy(int result, const char *operation);

    SDL_Renderer *renderer = nullptr;
    RenderStats stats;
};
