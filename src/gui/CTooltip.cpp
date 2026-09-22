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

#include "CTooltip.h"
#include "CGui.h"
#include "CTextManager.h"
#include "CTextureCache.h"
#include "core/CUtil.h"
#include "CUiTheme.h"

CTooltip::CTooltip() {
    setModal(true);
    setBackground("");
}

void CTooltip::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    if (!gui || !rect || !gui->getTextManager()) {
        return;
    }
    UiTheme::fill(gui->getRenderer(), *rect, UiTheme::Background);
    UiTheme::stroke(gui->getRenderer(), *rect, UiTheme::Accent);
    auto content = UiTheme::inset(rect, UiTheme::scaled(gui, 16));
    content->h = std::max(1, content->h - UiTheme::scaled(gui, 36));
    scrollMaximum = std::max(0, gui->getTextManager()->measureText(text, content->w).second - content->h);
    scrollOffset = std::clamp(scrollOffset, 0, scrollMaximum);
    gui->getTextManager()->drawTextStyled(text, content, "body", UiTheme::Text, false, -scrollOffset);
    gui->getTextManager()->drawTextStyled(
        "Esc / click: close · Scroll: read",
        CUtil::rect(content->x, content->y + content->h + 4, content->w, UiTheme::scaled(gui, 30)), "small",
        UiTheme::Muted);
}

bool CTooltip::mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) {
    if (type == SDL_MOUSEBUTTONDOWN && (button == SDL_BUTTON_LEFT || button == SDL_BUTTON_RIGHT)) {
        if (auto parent = getParent()) {
            parent->removeChild(this->ptr<CTooltip>());
        }
    }
    return true;
}

bool CTooltip::keyboardEvent(std::shared_ptr<CGui> gui, SDL_EventType type, SDL_Keycode key) {
    if (type == SDL_KEYDOWN) {
        if (key == SDLK_ESCAPE)
            removeParent();
        else if (key == SDLK_DOWN || key == SDLK_PAGEDOWN)
            scrollOffset = std::min(scrollMaximum, scrollOffset + 96);
        else if (key == SDLK_UP || key == SDLK_PAGEUP)
            scrollOffset = std::max(0, scrollOffset - 96);
    }
    return true;
}

bool CTooltip::mouseWheelEvent(std::shared_ptr<CGui>, SDL_EventType, int, int, int, int wheelY) {
    scrollOffset = static_cast<int>(
        std::clamp(static_cast<long long>(scrollOffset) - 64LL * wheelY, 0LL, static_cast<long long>(scrollMaximum)));
    return true;
}

void CTooltip::setText(std::string _text) { this->text = _text; }

std::string CTooltip::getText() { return text; }
