/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026 Andrzej Lis
SPDX-License-Identifier: GPL-3.0-or-later
*/
#pragma once
#include "core/CUtil.h"

#include "gui/CGui.h"
#include <algorithm>
#include <cmath>

namespace UiTheme {
inline constexpr SDL_Color Background{20, 23, 27, 255};
inline constexpr SDL_Color Panel{32, 37, 44, 255};
inline constexpr SDL_Color Selection{48, 56, 66, 255};
inline constexpr SDL_Color Text{242, 235, 221, 255};
inline constexpr SDL_Color Muted{184, 179, 170, 255};
inline constexpr SDL_Color Accent{197, 166, 106, 255};
inline constexpr SDL_Color Danger{232, 146, 142, 255};
inline constexpr SDL_Color Border{96, 103, 111, 255};
inline constexpr SDL_Color Success{154, 207, 172, 255};

inline int scaled(const std::shared_ptr<CGui> &gui, int value) {
    return std::max(1, static_cast<int>(std::lround(value * (gui ? gui->getUiScale() : 1.0))));
}

inline std::shared_ptr<SDL_Rect> inset(const std::shared_ptr<SDL_Rect> &rect, int padding) {
    return CUtil::rect(rect->x + padding, rect->y + padding, std::max(0, rect->w - 2 * padding),
                       std::max(0, rect->h - 2 * padding));
}

inline void fill(SDL_Renderer *renderer, const SDL_Rect &rect, SDL_Color color) {
    if (!renderer || rect.w <= 0 || rect.h <= 0)
        return;
    SDL_SetRenderDrawColor(renderer, color.r, color.g, color.b, color.a);
    SDL_RenderFillRect(renderer, &rect);
}

inline void stroke(SDL_Renderer *renderer, const SDL_Rect &rect, SDL_Color color) {
    if (!renderer || rect.w <= 0 || rect.h <= 0)
        return;
    SDL_SetRenderDrawColor(renderer, color.r, color.g, color.b, color.a);
    SDL_RenderDrawRect(renderer, &rect);
}
} // namespace UiTheme
