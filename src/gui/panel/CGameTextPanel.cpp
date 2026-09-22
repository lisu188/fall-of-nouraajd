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
#include "CGameTextPanel.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/CTextManager.h"
#include "gui/CUiTheme.h"

#include <algorithm>
#include <sstream>

std::string CGameTextPanel::getText() { return text; }

void CGameTextPanel::setText(std::string value) {
    text = std::move(value);
    scrollOffset = 0;
    measuredWidth = 0;
    if (getTitle().empty()) {
        setTitle(getTypeId() == "infoPanel" ? "Information" : "Message");
    }
}

void CGameTextPanel::measureContent(const std::shared_ptr<CGui> &gui, int width, int height) {
    int contentHeight = 0;
    if (measuredWidth != width || measuredScale != gui->getUiScale() || measuredTextScale != gui->getTextScale()) {
        paragraphs.clear();
        auto textManager = gui->getTextManager();
        const int lineHeight = textManager->measureText("Ag", width).second;
        std::istringstream lines(text);
        std::string line;
        while (std::getline(lines, line)) {
            std::size_t offset = 0;
            do {
                auto end = std::min(offset + 1024, line.size());
                while (end < line.size() && end > offset && (static_cast<unsigned char>(line[end]) & 0xc0) == 0x80) {
                    --end;
                }
                const auto part = line.substr(offset, end - offset);
                const int paragraphHeight = std::max(lineHeight, textManager->measureText(part, width).second);
                paragraphs.push_back({part, contentHeight, paragraphHeight});
                contentHeight += paragraphHeight;
                offset = end;
            } while (offset < line.size());
        }
        measuredWidth = width;
        measuredScale = gui->getUiScale();
        measuredTextScale = gui->getTextScale();
    } else if (!paragraphs.empty()) {
        contentHeight = paragraphs.back().y + paragraphs.back().height;
    }
    scrollMaximum = std::max(0, contentHeight - height);
    scrollOffset = std::clamp(scrollOffset, 0, scrollMaximum);
}

void CGameTextPanel::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int) {
    if (!gui || !rect || rect->w <= 0 || rect->h <= 0) {
        return;
    }
    const int padding = UiTheme::scaled(gui, 24);
    const int top = getShellHeaderHeight(gui) + UiTheme::scaled(gui, 16);
    auto textManager = gui->getTextManager();
    const int width = std::max(1, rect->w - padding * 2);
    const std::string buttonLabel = "Continue | PgUp / PgDn to read";
    const int buttonHeight = std::max(UiTheme::scaled(gui, 44),
                                      textManager->measureText(buttonLabel, width - padding).second + UiTheme::scaled(gui, 16));
    const int footer = buttonHeight + padding * 2;
    auto viewport = CUtil::rect(rect->x + padding, rect->y + top, std::max(1, rect->w - padding * 2),
                                std::max(1, rect->h - top - footer));
    measureContent(gui, viewport->w, viewport->h);
    bodyRect = viewport;
    if (centered && scrollMaximum == 0 && text.size() <= 1024) {
        textManager->drawTextStyled(text, viewport, "body", UiTheme::Text, true);
    } else {
        for (const auto &paragraph : paragraphs) {
            if (paragraph.y + paragraph.height > scrollOffset && paragraph.y < scrollOffset + viewport->h) {
                textManager->drawTextStyled(paragraph.text, viewport, "body", UiTheme::Text, false,
                                            paragraph.y - scrollOffset);
            }
        }
    }
    auto button = CUtil::rect(rect->x + padding, rect->y + rect->h - padding - buttonHeight, width, buttonHeight);
    continueRect = button;
    CUtil::setRenderDrawColor(gui->getRenderer(), UiTheme::Selection);
    SDL_RenderFillRect(gui->getRenderer(), button.get());
    textManager->drawTextStyled(scrollMaximum ? buttonLabel : "Continue", button, "body", UiTheme::Text, true);
}

bool CGameTextPanel::event(std::shared_ptr<CGui> gui, SDL_Event *event) {
    if (event && event->type == SDL_KEYDOWN && event->key.repeat &&
        (event->key.keysym.sym == SDLK_RETURN || event->key.keysym.sym == SDLK_SPACE ||
         event->key.keysym.sym == SDLK_ESCAPE)) {
        return true;
    }
    return CGamePanel::event(gui, event);
}

bool CGameTextPanel::keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode key) {
    if (type != SDL_KEYDOWN) {
        return true;
    }
    switch (key) {
    case SDLK_SPACE:
    case SDLK_RETURN:
    case SDLK_ESCAPE:
        close();
        break;
    case SDLK_UP:
        scrollOffset -= UiTheme::scaled(gui, 32);
        break;
    case SDLK_DOWN:
        scrollOffset += UiTheme::scaled(gui, 32);
        break;
    case SDLK_PAGEUP:
        scrollOffset -= UiTheme::scaled(gui, 240);
        break;
    case SDLK_PAGEDOWN:
        scrollOffset += UiTheme::scaled(gui, 240);
        break;
    case SDLK_HOME:
        scrollOffset = 0;
        break;
    case SDLK_END:
        scrollOffset = scrollMaximum;
        break;
    default:
        break;
    }
    scrollOffset = std::clamp(scrollOffset, 0, scrollMaximum);
    return true;
}

bool CGameTextPanel::mouseWheelEvent(std::shared_ptr<CGui> gui, SDL_EventType, int, int, int, int wheelY) {
    scrollOffset = std::clamp(scrollOffset - wheelY * UiTheme::scaled(gui, 64), 0, scrollMaximum);
    return true;
}

bool CGameTextPanel::mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) {
    if (button == SDL_BUTTON_LEFT && getLayout()) {
        auto rect = getLayout()->getRect(this->ptr<CGameGraphicsObject>());
        if (!continueRect) {
            renderObject(gui, rect, 0);
        }
        const bool inside = continueRect && x >= continueRect->x - rect->x &&
                            x < continueRect->x - rect->x + continueRect->w && y >= continueRect->y - rect->y &&
                            y < continueRect->y - rect->y + continueRect->h;
        if (type == SDL_MOUSEBUTTONDOWN) {
            continuePressed = inside;
            if (inside)
                return true;
        } else if (type == SDL_MOUSEBUTTONUP) {
            const bool activate = continuePressed && inside;
            continuePressed = false;
            if (activate) {
                close();
                return true;
            }
        }
    }
    return CGamePanel::mouseEvent(gui, type, button, x, y);
}

CGameTextPanel::~CGameTextPanel() {}

bool CGameTextPanel::getCentered() { return centered; }

void CGameTextPanel::setCentered(bool value) { centered = value; }
