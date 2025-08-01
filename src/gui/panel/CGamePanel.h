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

#include "gui/CGui.h"
#include "gui/object/CGameGraphicsObject.h"
#include "gui/panel/CListView.h"

class CWidget;

class CGamePanel : public CGameGraphicsObject {
  V_META(CGamePanel, CGameGraphicsObject, vstd::meta::empty())
public:
  CGamePanel();

  bool keyboardEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type,
                     SDL_Keycode i) override;

  bool mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type,
                  int button, int x, int y) override;

  void refreshViews();

  void awaitClosing();

  void close();
};
