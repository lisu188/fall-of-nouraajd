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
#include "CGameLootPanel.h"

void CGameLootPanel::setItems(const std::set<std::shared_ptr<CItem>> &_items) {
  items = _items;
}

CListView::collection_pointer
CGameLootPanel::itemsCollection(const std::shared_ptr<CGui> &gui) {
  return std::make_shared<CListView::collection_type>(
      vstd::cast<CListView::collection_type>(items));
}

std::set<std::shared_ptr<CItem>> CGameLootPanel::getItems() { return items; }

bool CGameLootPanel::keyboardEvent(std::shared_ptr<CGui> gui,
                                   SDL_EventType type, SDL_Keycode i) {
  if (type == SDL_KEYDOWN) {
    // TODO: get rid of this
    if (i == SDLK_SPACE) {
      close();
    }
  }
  return true;
}

const std::shared_ptr<CCreature> &CGameLootPanel::getCreature() const {
  return creature;
}

void CGameLootPanel::setCreature(const std::shared_ptr<CCreature> &_creature) {
  creature = _creature;
}
