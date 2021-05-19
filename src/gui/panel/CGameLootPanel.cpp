/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2021  Andrzej Lis

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

void CGameLootPanel::setItems(std::set<std::shared_ptr<CItem>> items) {
    this->items = items;
}

CListView::collection_pointer CGameLootPanel::itemsCollection(std::shared_ptr<CGui> gui) {
    return std::make_shared<CListView::collection_type>(vstd::cast<CListView::collection_type>(
            items));
}

std::set<std::shared_ptr<CItem>> CGameLootPanel::getItems() {
    return items;
}