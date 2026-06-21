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
#include "gui/CRenderContext.h"

namespace {
class RenderClipGuard {
  public:
    RenderClipGuard(SDL_Renderer *renderer, const SDL_Rect *clip) : renderer(renderer), enabled(clip != nullptr) {
        if (!renderer || !clip) {
            return;
        }
        previousClipEnabled = SDL_RenderIsClipEnabled(renderer);
        if (previousClipEnabled) {
            SDL_RenderGetClipRect(renderer, &previousClip);
        }
        const auto normalizedClip = CRenderContext::normalizeTargetRect(*clip);
        ready = SDL_RenderSetClipRect(renderer, &normalizedClip) == 0;
        if (!ready) {
            vstd::logger::error("CRenderContext: failed to set render clip", SDL_GetError());
        }
    }

    ~RenderClipGuard() {
        if (!renderer || !enabled || !ready) {
            return;
        }
        if (previousClipEnabled) {
            if (SDL_RenderSetClipRect(renderer, &previousClip) != 0) {
                vstd::logger::error("CRenderContext: failed to restore render clip", SDL_GetError());
            }
        } else if (SDL_RenderSetClipRect(renderer, nullptr) != 0) {
            vstd::logger::error("CRenderContext: failed to clear render clip", SDL_GetError());
        }
    }

    bool isReady() const { return ready; }

  private:
    SDL_Renderer *renderer = nullptr;
    bool enabled = false;
    bool ready = true;
    SDL_bool previousClipEnabled = SDL_FALSE;
    SDL_Rect previousClip = {0, 0, 0, 0};
};
} // namespace

CRenderContext::CRenderContext(SDL_Renderer *renderer) : renderer(renderer) {}

void CRenderContext::setRenderer(SDL_Renderer *renderer) { this->renderer = renderer; }

SDL_Renderer *CRenderContext::getRenderer() const { return renderer; }

bool CRenderContext::copy(SDL_Texture *texture, const SDL_Rect *sourceRect, const SDL_Rect *targetRect,
                          const SDL_Rect *clipRect) {
    SDL_Rect normalizedTarget;
    if (!prepareCopy(texture, targetRect, normalizedTarget, "CRenderContext::copy")) {
        return false;
    }
    RenderClipGuard clipGuard(renderer, clipRect);
    if (!clipGuard.isReady()) {
        ++stats.failedCopies;
        return false;
    }
    return finishCopy(SDL_RenderCopy(renderer, texture, sourceRect, &normalizedTarget), "CRenderContext::copy");
}

bool CRenderContext::copy(SDL_Texture *texture, const SDL_Rect *sourceRect, const SDL_Rect &targetRect,
                          const SDL_Rect *clipRect) {
    return copy(texture, sourceRect, &targetRect, clipRect);
}

bool CRenderContext::copyEx(SDL_Texture *texture, const SDL_Rect *sourceRect, const SDL_Rect *targetRect, double angle,
                            const SDL_Point *center, SDL_RendererFlip flip, const SDL_Rect *clipRect) {
    SDL_Rect normalizedTarget;
    if (!prepareCopy(texture, targetRect, normalizedTarget, "CRenderContext::copyEx")) {
        return false;
    }
    RenderClipGuard clipGuard(renderer, clipRect);
    if (!clipGuard.isReady()) {
        ++stats.failedCopies;
        return false;
    }
    return finishCopy(SDL_RenderCopyEx(renderer, texture, sourceRect, &normalizedTarget, angle, center, flip),
                      "CRenderContext::copyEx");
}

bool CRenderContext::copyEx(SDL_Texture *texture, const SDL_Rect *sourceRect, const SDL_Rect &targetRect, double angle,
                            const SDL_Point *center, SDL_RendererFlip flip, const SDL_Rect *clipRect) {
    return copyEx(texture, sourceRect, &targetRect, angle, center, flip, clipRect);
}

const CRenderContext::RenderStats &CRenderContext::getStats() const { return stats; }

void CRenderContext::resetStats() { stats = {}; }

SDL_Rect CRenderContext::normalizeTargetRect(const SDL_Rect &rect) {
    SDL_Rect normalized = rect;
    if (normalized.w < 0) {
        normalized.x += normalized.w;
        normalized.w = -normalized.w;
    }
    if (normalized.h < 0) {
        normalized.y += normalized.h;
        normalized.h = -normalized.h;
    }
    return normalized;
}

bool CRenderContext::prepareCopy(SDL_Texture *texture, const SDL_Rect *targetRect, SDL_Rect &normalizedTarget,
                                 const char *operation) {
    ++stats.attemptedCopies;
    if (!renderer) {
        ++stats.skippedCopies;
        vstd::logger::error(operation, "missing renderer");
        return false;
    }
    if (!texture) {
        ++stats.skippedCopies;
        vstd::logger::error(operation, "missing texture");
        return false;
    }
    if (!targetRect) {
        ++stats.skippedCopies;
        vstd::logger::error(operation, "missing target rect");
        return false;
    }
    normalizedTarget = normalizeTargetRect(*targetRect);
    if (normalizedTarget.w <= 0 || normalizedTarget.h <= 0) {
        ++stats.skippedCopies;
        vstd::logger::warning(operation, "empty target rect", normalizedTarget.x, normalizedTarget.y,
                              normalizedTarget.w, normalizedTarget.h);
        return false;
    }
    return true;
}

bool CRenderContext::finishCopy(int result, const char *operation) {
    if (result != 0) {
        ++stats.failedCopies;
        vstd::logger::error(operation, "failed", SDL_GetError());
        return false;
    }
    ++stats.successfulCopies;
    return true;
}
