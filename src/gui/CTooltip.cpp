/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

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

void CTooltip::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    SDL_RenderCopy(gui->getRenderer(), gui->getTextureCache()->getTexture("images/tooltip.png"), nullptr, rect.get());
    gui->getTextManager()->drawTextCentered(text, rect);
}

bool CTooltip::mouseEvent(std::shared_ptr<CGui> gui, SDL_EventType type, int button, int x, int y) {
    if (type == SDL_MOUSEBUTTONUP && button == SDL_BUTTON_RIGHT) {
        getParent()->removeChild(this->ptr<CTooltip>());
    }
    return true;
}

bool CTooltip::keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, SDL_Keycode i) {
    return true;
}

void CTooltip::setText(std::string _text) {
    this->text = _text;
}

std::string CTooltip::getText() {
    return text;
}