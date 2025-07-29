/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025  Andrzej Lis

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
#include "gui/CGui.h"
#include "gui/CTextManager.h"
#include "object/CPlayer.h"

void CStatsGraphicsUtil::drawStats(std::shared_ptr<CGui> gui,
                                   std::shared_ptr<CCreature> creature, int x,
                                   int y, int w, int h, bool showNumeric,
                                   bool showExp) {

  drawBar(gui, creature->getHpRatio(), 0, RED, x, y, w, h);
  if (showNumeric) {
    drawValues(gui, creature->getHp(), creature->getHpMax(), 0, x, y, w, h);
  }
  drawBar(gui, creature->getManaRatio(), 1, BLUE, x, y, w, h);
  if (showNumeric) {
    drawValues(gui, creature->getMana(), creature->getManaMax(), 1, x, y, w, h);
  }
  if (showExp) {
    drawBar(gui, creature->getExpRatio(), 2, YELLOW, x, y, w, h);
    if (showNumeric) {
      drawValues(gui, creature->getExp(), creature->getExpForNextLevel(), 2, x,
                 y, w, h);
    }
  }
}

void CStatsGraphicsObject::renderObject(std::shared_ptr<CGui> gui,
                                        std::shared_ptr<SDL_Rect> rect,
                                        int frameTime) {
  auto cret = creature->invoke<CCreature>(gui->getGame(), this->ptr());
  CStatsGraphicsUtil::drawStats(gui, cret, rect->x, rect->y, rect->w, rect->h,
                                true, true);
}

CStatsGraphicsObject::CStatsGraphicsObject() {}

std::shared_ptr<CScript> CStatsGraphicsObject::getCreature() {
  return creature;
}

void CStatsGraphicsObject::setCreature(std::shared_ptr<CScript> _creature) {
  creature = _creature;
}

void CStatsGraphicsUtil::drawBar(std::shared_ptr<CGui> gui, int ratio,
                                 int index, Uint8 r, Uint8 g, Uint8 b, Uint8 a,
                                 int x, int y, int w, int h) {
  h = h / 3.0;
  SDL_Rect filledBar;
  filledBar.x = x;
  filledBar.y = y + index * h;
  filledBar.h = h;
  filledBar.w = (int)(ratio / 100.0 * w);

  SDL_SetRenderDrawColor(gui->getRenderer(), r, g, b, a);
  SDL_RenderFillRect(gui->getRenderer(), &filledBar);

  SDL_Rect emptyBar;
  emptyBar.x = x + filledBar.w;
  emptyBar.y = y + index * h;
  emptyBar.h = h;
  emptyBar.w = w - filledBar.w;

  SDL_SetRenderDrawColor(gui->getRenderer(), BLACK);
  SDL_RenderFillRect(gui->getRenderer(), &emptyBar);
}

void CStatsGraphicsUtil::drawValues(std::shared_ptr<CGui> gui, int left,
                                    int right, int index, int x, int y, int w,
                                    int h) {
  h = h / 3.0;
  gui->getTextManager()->drawTextCentered(
      vstd::str(left) + "/" + vstd::str(right), x, y + index * h, w, h);
}

bool CStatsGraphicsObject::mouseEvent(std::shared_ptr<CGui> sharedPtr,
                                      SDL_EventType type, int button, int x,
                                      int y) {
  return true;
}