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

#include "CGamePanel.h"
#include "core/CList.h"

#include <string>
#include <utility>
#include <vector>

class CPlayer;

class CGameCharacterPanel : public CGamePanel {
    V_META(CGameCharacterPanel, CGamePanel,
           V_PROPERTY(CGameCharacterPanel, std::shared_ptr<CMapStringString>, charSheet, getCharSheet, setCharSheet),
           V_METHOD(CGameCharacterPanel, interactionsCollection, CListView::collection_pointer, std::shared_ptr<CGui>))

    void renderObject(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> rect, int i) override;

  public:
    // Render-free text assembly for the character sheet: resolves the configured
    // charSheet accessors against the player and returns the ordered label/value
    // rows renderObject draws. Kept separate from rendering so the panel text is
    // unit-testable without SDL and so later identity rows (race / class labels)
    // can extend the row list in one place.
    std::vector<std::pair<std::string, std::string>> buildCharacterSheetLines(const std::shared_ptr<CPlayer> &player);

    std::shared_ptr<CMapStringString> getCharSheet();

    void setCharSheet(std::shared_ptr<CMapStringString> charSheet);

    ~CGameCharacterPanel();

    CListView::collection_pointer interactionsCollection(std::shared_ptr<CGui> gui);

  private:
    std::shared_ptr<CMapStringString> charSheet;
};
