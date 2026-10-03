/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026 Andrzej Lis
SPDX-License-Identifier: GPL-3.0-or-later
*/
#pragma once

#include "gui/CGui.h"
#include "gui/CTextureCache.h"
#include <algorithm>

namespace UiArtwork {
inline bool validPath(const std::string &path) {
    return path.starts_with("images/") && path.ends_with(".png") && path.find("..") == std::string::npos &&
           path.find('\\') == std::string::npos && path.find(':') == std::string::npos;
}

inline SDL_Texture *texture(const std::shared_ptr<CGui> &gui, const std::string &path) {
    return gui && validPath(path) ? gui->getTextureCache()->getTexture(path) : nullptr;
}

inline SDL_Rect fit(int width, int height, const SDL_Rect &bounds) {
    if (width <= 0 || height <= 0 || bounds.w <= 0 || bounds.h <= 0)
        return {bounds.x, bounds.y, 0, 0};
    const double scale = std::min(static_cast<double>(bounds.w) / width, static_cast<double>(bounds.h) / height);
    const int fittedWidth = std::max(1, static_cast<int>(width * scale));
    const int fittedHeight = std::max(1, static_cast<int>(height * scale));
    return {bounds.x + (bounds.w - fittedWidth) / 2, bounds.y + (bounds.h - fittedHeight) / 2, fittedWidth,
            fittedHeight};
}

struct Layout {
    SDL_Rect image{0, 0, 0, 0};
    SDL_Rect text{0, 0, 0, 0};
    int inset = 0;
};

inline Layout layout(const std::shared_ptr<CGui> &gui, SDL_Texture *image, SDL_Rect bounds, bool compact) {
    Layout result{{0, 0, 0, 0}, bounds, 0};
    int width = 0, height = 0;
    if (!image || SDL_QueryTexture(image, nullptr, nullptr, &width, &height) != 0 || width <= 0 || height <= 0)
        return result;
    const int gap = std::max(16, gui->getHeight() * 16 / 1080);
    auto imageBounds = bounds;
    if (compact) {
        imageBounds.h = std::min(bounds.h / 4, std::max(96, gui->getHeight() * 128 / 1080));
        result.inset = imageBounds.h + gap;
    } else {
        imageBounds.w = bounds.w / 3;
        result.text.x += imageBounds.w + gap;
        result.text.w -= imageBounds.w + gap;
    }
    result.image = fit(width, height, imageBounds);
    return result;
}

inline void draw(const std::shared_ptr<CGui> &gui, SDL_Texture *image, SDL_Rect bounds, const SDL_Rect &clip,
                 int offset) {
    if (!image || bounds.w <= 0 || bounds.h <= 0)
        return;
    bounds.y -= offset;
    gui->getRenderContext().copy(image, nullptr, &bounds, &clip);
}
} // namespace UiArtwork
