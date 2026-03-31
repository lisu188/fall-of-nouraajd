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
#include "CGameFightPanel.h"
#include "core/CMap.h"
#include "gui/CAnimation.h"
#include "gui/CTextureCache.h"
#include "gui/object/CStatsGraphicsObject.h"

CListView::collection_pointer
CGameFightPanel::interactionsCollection(std::shared_ptr<CGui> gui) {
  return std::make_shared<CListView::collection_type>(
      vstd::cast<CListView::collection_type>(
          gui->getGame()->getMap()->getPlayer()->getInteractions()));
}

void CGameFightPanel::interactionsCallback(
    std::shared_ptr<CGui> gui, int index,
    std::shared_ptr<CGameObject> _newSelection) {
  auto newSelection = vstd::cast<CInteraction>(_newSelection);
  if (selected.lock() != newSelection &&
      newSelection->getManaCost() <=
          gui->getGame()->getMap()->getPlayer()->getMana()) {
    selected = newSelection;
  } else if (newSelection && selected.lock() == newSelection &&
             newSelection->getManaCost() <=
                 gui->getGame()->getMap()->getPlayer()->getMana()) {
    finalSelected = newSelection;
  } else {
    // TODO: rethink moving selection to CListView
    selected.reset();
  }
  refreshViews();
}

bool CGameFightPanel::interactionsSelect(std::shared_ptr<CGui> gui, int index,
                                         std::shared_ptr<CGameObject> object) {
  return selected.lock() && selected.lock() == object;
}

CListView::collection_pointer
CGameFightPanel::itemsCollection(std::shared_ptr<CGui> gui) {
  return std::make_shared<CListView::collection_type>(
      vstd::cast<CListView::collection_type>(
          gui->getGame()->getMap()->getPlayer()->getItems()));
}

void CGameFightPanel::itemsCallback(
    std::shared_ptr<CGui> gui, int index,
    std::shared_ptr<CGameObject> _newSelection) {
  auto newSelection = vstd::cast<CItem>(_newSelection);
  if (newSelection && newSelection->hasTag(CTag::Quest)) {
    return;
  }
  if (selectedItem.lock() != newSelection) {
    selectedItem = newSelection;
  } else if (selectedItem.lock() && selectedItem.lock() == newSelection) {
    gui->getGame()->getMap()->getPlayer()->useItem(newSelection);
    selectedItem.reset();
  }
  refreshViews();
}

bool CGameFightPanel::itemsRightClickCallback(
    std::shared_ptr<CGui> gui, int index,
    std::shared_ptr<CGameObject> _newSelection) {
  auto newSelection = vstd::cast<CItem>(_newSelection);
  if (!newSelection || newSelection->hasTag(CTag::Quest)) {
    return false;
  }
  gui->getGame()->getMap()->getPlayer()->useItem(newSelection);
  selectedItem.reset();
  refreshViews();
  return true;
}

bool CGameFightPanel::itemsSelect(std::shared_ptr<CGui> gui, int index,
                                  std::shared_ptr<CGameObject> object) {
  return object && !object->hasTag(CTag::Quest) && selectedItem.lock() &&
         selectedItem.lock() == object;
}

CGameFightPanel::CGameFightPanel() {}

bool CGameFightPanel::mouseEvent(std::shared_ptr<CGui> gui,
                                 SDL_EventType type, int button, int x,
                                 int y) {
  if (type == SDL_MOUSEBUTTONDOWN && button == SDL_BUTTON_RIGHT) {
    selected.reset();
    selectedItem.reset();
    finalSelected.reset();
    refreshViews();
  }
  return true;
}

std::shared_ptr<CInteraction> CGameFightPanel::selectInteraction() {
  auto self = this->ptr<CGameFightPanel>();
  vstd::call_later_block([self]() {
    while (self->finalSelected.lock() == nullptr) {
      auto gui = self->getGui();
      if (!gui || gui->findChild(self) == nullptr) {
        return;
      }
      if (!vstd::event_loop<>::instance()->run()) {
        SDL_Event quit_event;
        SDL_zero(quit_event);
        quit_event.type = SDL_QUIT;
        SDL_PushEvent(&quit_event);
        return;
      }
    }
  });
  auto ret = self->finalSelected.lock();
  self->finalSelected.reset();
  self->selected.reset();
  self->refreshViews();
  return ret;
}

std::shared_ptr<CCreature> CGameFightPanel::getEnemy() { return enemy.lock(); }

void CGameFightPanel::setEnemy(std::shared_ptr<CCreature> en) { enemy = en; }
