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
#pragma once

#include "object/CPlayer.h"
#include "CGamePanel.h"
#include "gui/panel/CListView.h"

class CGameFightPanel : public CGamePanel {
V_META(CGameFightPanel, CGamePanel,
       V_METHOD(CGameFightPanel, interactionsCollection, CListView::collection_pointer, std::shared_ptr<CGui>),
       V_METHOD(CGameFightPanel, interactionsCallback, void, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>),
       V_METHOD(CGameFightPanel, interactionsSelect, bool, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>),
       V_METHOD(CGameFightPanel, itemsCollection, CListView::collection_pointer, std::shared_ptr<CGui>),
       V_METHOD(CGameFightPanel, itemsCallback, void, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>),
       V_METHOD(CGameFightPanel, itemsSelect, bool, std::shared_ptr<CGui>, int, std::shared_ptr<CGameObject>),
       V_METHOD(CGameFightPanel, getEnemy, std::shared_ptr<CCreature>))

public:
    CGameFightPanel();

    std::shared_ptr<CInteraction> selectInteraction();

    std::shared_ptr<CCreature> getEnemy();

    void setEnemy(std::shared_ptr<CCreature> en);

private:
    std::weak_ptr<CCreature> enemy;
    std::weak_ptr<CInteraction> selected;
    std::weak_ptr<CItem> selectedItem;
    std::weak_ptr<CInteraction> finalSelected;

    void drawEnemy(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pRect, int frameTime);

public:
    CListView::collection_pointer interactionsCollection(std::shared_ptr<CGui> gui);

    void interactionsCallback(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> _newSelection);

    bool interactionsSelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object);

    CListView::collection_pointer itemsCollection(std::shared_ptr<CGui> gui);

    void itemsCallback(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> _newSelection);

    bool itemsSelect(std::shared_ptr<CGui> gui, int index, std::shared_ptr<CGameObject> object);
};

