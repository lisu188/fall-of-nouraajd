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
#include "CGamePanel.h"
#include "gui/CGui.h"
#include "core/CWidget.h"


void CGamePanel::render(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pos, int frameTime) {
    std::shared_ptr<SDL_Rect> rect = getRect(pos);
    SDL_RenderFillRect(gui->getRenderer(), rect.get());
    SDL_RenderCopy(gui->getRenderer(), gui->getTextureCache()->getTexture("images/panel.png"), nullptr, rect.get());
    this->panelRender(gui, rect, frameTime);
}

void CGamePanel::panelRender(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> pRect, int i) {
    for (auto widget:widgets) {
        this->meta()->invoke_method<void, CGamePanel,
                std::shared_ptr<CGui>,
                std::shared_ptr<SDL_Rect>, int>(widget->getRender(),
                                                this->ptr<CGamePanel>(), shared_ptr,
                                                widget->getRect(pRect), i);
    }
}

void CGamePanel::panelKeyboardEvent(std::shared_ptr<CGui> shared_ptr, SDL_Keycode i) {

}

void CGamePanel::panelMouseEvent(std::shared_ptr<CGui> gui, int x, int y) {
    for (auto widget:widgets) {
        if (CUtil::isIn(widget->getRect(RECT(0, 0, getWidth(), getHeight())), x, y)) {
            this->meta()->invoke_method<void, CGamePanel,
                    std::shared_ptr<CGui>>(widget->getClick(),
                                           this->ptr<CGamePanel>(),
                                           gui);
        }
    }
}


std::set<std::shared_ptr<CWidget>> CGamePanel::getWidgets() {
    return widgets;
}

void CGamePanel::setWidgets(std::set<std::shared_ptr<CWidget>> widgets) {
    CGamePanel::widgets = widgets;
}