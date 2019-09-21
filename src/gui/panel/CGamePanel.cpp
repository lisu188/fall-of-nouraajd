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

int CGamePanel::getXSize() {
    return xSize;
}

void CGamePanel::setXSize(int _xSize) {
    xSize = _xSize;
}

int CGamePanel::getYSize() {
    return ySize;
}

void CGamePanel::setYSize(int _ySize) {
    ySize = _ySize;
}

void CGamePanel::render(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pos, int frameTime) {
    std::shared_ptr<SDL_Rect> rect = getPanelRect(pos);
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

bool CGamePanel::event(std::shared_ptr<CGui> gui, SDL_Event *event) {
    if (!CGameGraphicsObject::event(gui, event)) {
        //TODO: rethink moving this to upper level soe every object can use events
        if (event->type == SDL_KEYDOWN) {
            this->panelKeyboardEvent(gui, event->key.keysym.sym);
        } else if (event->type == SDL_MOUSEBUTTONDOWN) {
            std::pair<int, int> translated = translatePos(gui, event->button.x, event->button.y);
            if (translated.first >= 0 && translated.first < xSize && translated.second >= 0 &&
                translated.second < ySize) {
                this->panelMouseEvent(gui, translated.first, translated.second);
            }
        }
    }
    return true;
}


std::shared_ptr<SDL_Rect> CGamePanel::getPanelRect(std::shared_ptr<SDL_Rect> pos) {
    //TODO: useBoxInBox
    return RECT(
            pos->x + pos->w / 2 - this->xSize / 2,
            pos->y + pos->h / 2 - this->ySize / 2,
            xSize,
            ySize);
}

std::pair<int, int> CGamePanel::translatePos(std::shared_ptr<CGui> gui, int x, int y) {
    std::shared_ptr<SDL_Rect> transPos = getPanelRect(RECT(0, 0, gui->getWidth(), gui->getHeight()));
    return std::make_pair<int, int>(x - transPos->x, y - transPos->y);
}

void CGamePanel::panelKeyboardEvent(std::shared_ptr<CGui> shared_ptr, SDL_Keycode i) {

}

void CGamePanel::panelMouseEvent(std::shared_ptr<CGui> gui, int x, int y) {
    for (auto widget:widgets) {
        if (CUtil::isIn(widget->getRect(RECT(0, 0, getXSize(), getYSize())), x, y)) {
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