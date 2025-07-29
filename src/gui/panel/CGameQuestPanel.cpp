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
#include "CGameQuestPanel.h"
#include "core/CMap.h"
#include "gui/CGui.h"
#include "gui/CTextManager.h"

void CGameQuestPanel::renderObject(std::shared_ptr<CGui> gui,
                                   std::shared_ptr<SDL_Rect> rect, int i) {
  gui->getTextManager()->drawText(getText(gui), rect->x, rect->y, rect->w);
}

std::string CGameQuestPanel::getText(std::shared_ptr<CGui> ptr) {
  std::string text = "";
  for (auto quest :
       ptr->getGame()->getMap()->getPlayer()->getCompletedQuests()) {
    text += quest->getDescription();
    text += "(completed)";
    text += "\n";
  }
  for (auto quest : ptr->getGame()->getMap()->getPlayer()->getQuests()) {
    text += quest->getDescription();
    text += "\n";
  }
  return text;
}
