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
#pragma once

#include <vector>

#include "CGamePanel.h"
#include "gui/panel/CListView.h"
#include "object/CPlayer.h"

class CGameFightPanel : public CGamePanel {
  V_META(CGameFightPanel, CGamePanel,
         V_METHOD(CGameFightPanel, interactionsCollection,
                  CListView::collection_pointer, std::shared_ptr<CGui>),
         V_METHOD(CGameFightPanel, interactionsCallback, void,
                  std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>),
         V_METHOD(CGameFightPanel, interactionsSelect, bool,
                  std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>),
         V_METHOD(CGameFightPanel, itemsCollection,
                  CListView::collection_pointer, std::shared_ptr<CGui>),
         V_METHOD(CGameFightPanel, itemsCallback, void, std::shared_ptr<CGui>,
                  int, std::shared_ptr<CGameObject>),
         V_METHOD(CGameFightPanel, itemsSelect, bool, std::shared_ptr<CGui>,
                  int, std::shared_ptr<CGameObject>),
         V_METHOD(CGameFightPanel, enemiesCollection,
                  CListView::collection_pointer, std::shared_ptr<CGui>),
         V_METHOD(CGameFightPanel, enemiesCallback, void, std::shared_ptr<CGui>,
                  int, std::shared_ptr<CGameObject>),
         V_METHOD(CGameFightPanel, enemiesSelect, bool, std::shared_ptr<CGui>,
                  int, std::shared_ptr<CGameObject>),
         V_METHOD(CGameFightPanel, getEnemy, std::shared_ptr<CCreature>))

public:
  CGameFightPanel();

  std::shared_ptr<CInteraction> selectInteraction();

  std::shared_ptr<CCreature> getEnemy();

  void setEnemy(std::shared_ptr<CCreature> en);

  void setEnemies(const std::vector<std::shared_ptr<CCreature>> &value);

private:
  std::vector<std::shared_ptr<CCreature>> enemies;
  std::weak_ptr<CCreature> enemy;
  std::weak_ptr<CInteraction> selected;
  std::weak_ptr<CItem> selectedItem;
  std::weak_ptr<CInteraction> finalSelected;
  bool mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type,
                  int button, int x, int y) override;

  void refreshEncounterViews();

public:
  CListView::collection_pointer
  interactionsCollection(std::shared_ptr<CGui> gui);

  void interactionsCallback(std::shared_ptr<CGui> gui, int index,
                            std::shared_ptr<CGameObject> _newSelection);

  bool interactionsSelect(std::shared_ptr<CGui> gui, int index,
                          std::shared_ptr<CGameObject> object);

  CListView::collection_pointer itemsCollection(std::shared_ptr<CGui> gui);

  void itemsCallback(std::shared_ptr<CGui> gui, int index,
                     std::shared_ptr<CGameObject> _newSelection);

  bool itemsSelect(std::shared_ptr<CGui> gui, int index,
                   std::shared_ptr<CGameObject> object);

  CListView::collection_pointer enemiesCollection(std::shared_ptr<CGui> gui);

  void enemiesCallback(std::shared_ptr<CGui> gui, int index,
                       std::shared_ptr<CGameObject> _newSelection);

  bool enemiesSelect(std::shared_ptr<CGui> gui, int index,
                     std::shared_ptr<CGameObject> object);
};
