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
#include "CGameGraphicsObject.h"
#include "gui/CGui.h"

void CGameGraphicsObject::render(std::shared_ptr<CGui> reneder, std::shared_ptr<SDL_Rect> pos, int frameTime) {

}

bool CGameGraphicsObject::event(std::shared_ptr<CGui> gui, SDL_Event *event) {
    for (auto callback:eventCallbackList) {
        if (callback.first(gui, event) && callback.second(gui, event)) {
            return true;
        }
    }
    if (event->type == SDL_KEYDOWN) {
        return this->keyboardEvent(gui, event->key.keysym.sym);
    } else if (event->type == SDL_MOUSEBUTTONDOWN) {
        std::pair<int, int> translated = translatePos(gui, event->button.x, event->button.y);
        if (translated.first >= 0 && translated.first < width && translated.second >= 0 &&
            translated.second < height) {
            return this->mouseEvent(gui, translated.first, translated.second);
        }
    }
    return false;
}

void
CGameGraphicsObject::registerEventCallback(std::function<bool(std::shared_ptr<CGui>, SDL_Event *)> pred,
                                           std::function<bool(std::shared_ptr<CGui>, SDL_Event *)> func) {
    eventCallbackList.emplace_back(pred, func);
}

std::pair<int, int> CGameGraphicsObject::translatePos(std::shared_ptr<CGui> gui, int x, int y) {
    std::shared_ptr<SDL_Rect> transPos = getRect(RECT(0, 0, parent.lock()->getWidth(), parent.lock()->getHeight()));
    return std::make_pair<int, int>(x - transPos->x, y - transPos->y);
}
