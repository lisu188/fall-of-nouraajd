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
#include "CStatsGraphicsObject.h"
#include "core/CMap.h"
#include "core/CScript.h"
#include "core/CUtil.h"
#include "gui/CGui.h"
#include "gui/CTextManager.h"
#include "object/CPlayer.h"

void CStatsGraphicsUtil::drawStats(std::shared_ptr<CGui> gui, std::shared_ptr<CCreature> creature, int x, int y, int w,
                                   int h, bool showNumeric, bool showExp) {
    if (!creature) {
        return;
    }

    const int barCount = showExp ? 3 : 2;

    drawBar(gui, creature->getHpRatio(), 0, barCount, CColors::Red, x, y, w, h);
    if (showNumeric) {
        drawValues(gui, creature->getHp(), creature->getHpMax(), 0, barCount, x, y, w, h);
    }
    drawBar(gui, creature->getManaRatio(), 1, barCount, CColors::Blue, x, y, w, h);
    if (showNumeric) {
        drawValues(gui, creature->getMana(), creature->getManaMax(), 1, barCount, x, y, w, h);
    }
    if (showExp) {
        drawBar(gui, creature->getExpRatio(), 2, barCount, CColors::Yellow, x, y, w, h);
        if (showNumeric) {
            drawValues(gui, creature->getExp(), creature->getExpForNextLevel(), 2, barCount, x, y, w, h);
        }
    }
}

void CStatsGraphicsObject::renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect, int frameTime) {
    auto cret = creature->invoke<CCreature>(gui->getGame(), this->ptr());
    CStatsGraphicsUtil::drawStats(gui, cret, rect->x, rect->y, rect->w, rect->h, true, true);
}

CStatsGraphicsObject::CStatsGraphicsObject() {}

std::shared_ptr<CScript> CStatsGraphicsObject::getCreature() { return creature; }

void CStatsGraphicsObject::setCreature(std::shared_ptr<CScript> _creature) { creature = _creature; }

void CStatsGraphicsUtil::drawBar(std::shared_ptr<CGui> gui, int ratio, int index, int barCount, SDL_Color color, int x,
                                 int y, int w, int h) {
    h = h / std::max(1, barCount);
    SDL_Rect filledBar;
    filledBar.x = x;
    filledBar.y = y + index * h;
    filledBar.h = h;
    filledBar.w = (int)(ratio / 100.0 * w);

    CUtil::setRenderDrawColor(gui->getRenderer(), color);
    SDL_RenderFillRect(gui->getRenderer(), &filledBar);

    SDL_Rect emptyBar;
    emptyBar.x = x + filledBar.w;
    emptyBar.y = y + index * h;
    emptyBar.h = h;
    emptyBar.w = w - filledBar.w;

    CUtil::setRenderDrawColor(gui->getRenderer(), CColors::Black);
    SDL_RenderFillRect(gui->getRenderer(), &emptyBar);
}

void CStatsGraphicsUtil::drawValues(std::shared_ptr<CGui> gui, int left, int right, int index, int barCount, int x,
                                    int y, int w, int h) {
    h = h / std::max(1, barCount);
    gui->getTextManager()->drawTextCentered(vstd::str(left) + "/" + vstd::str(right), x, y + index * h, w, h);
}

bool CStatsGraphicsObject::mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type, int button, int x, int y) {
    return true;
}
