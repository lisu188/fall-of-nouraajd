/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026 Andrzej Lis
SPDX-License-Identifier: GPL-3.0-or-later
*/
#pragma once

#include "gui/CTextManager.h"
#include "gui/CUiTheme.h"

#include <algorithm>
#include <sstream>
#include <vector>

namespace DetailViewport {
class Layout {
  public:
    struct Paragraph {
        std::string text;
        int y;
        int height;
    };

    bool update(const std::shared_ptr<CGui> &gui, const std::string &text, int width) {
        auto textManager = gui->getTextManager();
        width = std::max(1, width);
        if (measuredText == text && measuredWidth == width && measuredScale == gui->getTextScale() &&
            measuredManager.lock() == textManager) {
            return false;
        }
        paragraphs.clear();
        contentHeight = 0;
        const int lineHeight = std::max(1, textManager->measureText("Ag", width).second);
        std::istringstream lines(text);
        std::string line;
        while (std::getline(lines, line)) {
            std::size_t offset = 0;
            do {
                auto end = std::min(offset + 1024, line.size());
                while (end < line.size() && end > offset && (static_cast<unsigned char>(line[end]) & 0xc0) == 0x80) {
                    --end;
                }
                if (end == offset && offset < line.size()) {
                    end = std::min(offset + 1024, line.size());
                }
                auto chunk = line.substr(offset, end - offset);
                const int height =
                    chunk.empty() ? lineHeight : std::max(lineHeight, textManager->measureText(chunk, width).second);
                paragraphs.push_back({std::move(chunk), contentHeight, height});
                contentHeight += height;
                offset = end;
            } while (offset < line.size());
        }
        measuredText = text;
        measuredWidth = width;
        measuredScale = gui->getTextScale();
        measuredManager = textManager;
        return true;
    }

    int getContentHeight() const { return contentHeight; }
    const std::vector<Paragraph> &getParagraphs() const { return paragraphs; }

    void draw(const std::shared_ptr<CGui> &gui, const std::shared_ptr<SDL_Rect> &viewport, int offset) const {
        auto paragraph =
            std::lower_bound(paragraphs.begin(), paragraphs.end(), offset,
                             [](const Paragraph &value, int top) { return value.y + value.height <= top; });
        for (; paragraph != paragraphs.end() && paragraph->y < offset + viewport->h; ++paragraph) {
            gui->getTextManager()->drawTextScrolled(paragraph->text, viewport, paragraph->y - offset);
        }
    }

  private:
    std::vector<Paragraph> paragraphs;
    std::string measuredText;
    int measuredWidth = -1;
    double measuredScale = -1;
    std::weak_ptr<CTextManager> measuredManager;
    int contentHeight = 0;
};

inline std::shared_ptr<SDL_Rect> contentRect(const std::shared_ptr<CGui> &gui, const std::shared_ptr<SDL_Rect> &rect,
                                             int contentHeight) {
    auto content = CUtil::rect(rect->x, rect->y, rect->w, rect->h);
    if (contentHeight > rect->h) {
        const int hintHeight = gui->getTextManager()
                                   ->measureText("Scroll: wheel / PgUp / PgDn - 100%", std::max(1, rect->w), "small")
                                   .second;
        content->h = std::max(1, rect->h - hintHeight - UiTheme::scaled(gui, 4));
    }
    return content;
}

inline void drawScrollHint(const std::shared_ptr<CGui> &gui, const std::shared_ptr<SDL_Rect> &rect,
                           const std::shared_ptr<SDL_Rect> &content, int offset, int maximum) {
    if (maximum <= 0 || content->h >= rect->h)
        return;
    const int gap = UiTheme::scaled(gui, 4);
    const int top = content->y + content->h + gap;
    const auto hint = CUtil::rect(rect->x, top, rect->w, std::max(1, rect->y + rect->h - top));
    gui->getTextManager()->drawTextStyled("Scroll: wheel / PgUp / PgDn - " + std::to_string(100LL * offset / maximum) +
                                              "%",
                                          hint, "small", UiTheme::Muted);
}
} // namespace DetailViewport
