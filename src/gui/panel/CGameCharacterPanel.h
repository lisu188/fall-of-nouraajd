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

#include "CGamePanel.h"
#include "core/CList.h"

class CGameCharacterPanel : public CGamePanel {
V_META(CGameCharacterPanel, CGamePanel,
       V_PROPERTY(CGameCharacterPanel, std::shared_ptr<CListString>, charSheet, getCharSheet, setCharSheet))

    void renderObject(std::shared_ptr<CGui> shared_ptr, std::shared_ptr<SDL_Rect> rect, int i) override;

public:

    std::shared_ptr<CListString> getCharSheet();

    void setCharSheet(std::shared_ptr<CListString> charSheet);

    ~CGameCharacterPanel();

private:
    std::shared_ptr<CListString> charSheet;
};

