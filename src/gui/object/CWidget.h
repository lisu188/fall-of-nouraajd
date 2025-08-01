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

#include "gui/object/CGameGraphicsObject.h"

class CGui;

class CWidget : public CGameGraphicsObject {
  V_META(CWidget, CGameGraphicsObject,
         V_PROPERTY(CWidget, std::string, render, getRender, setRender),
         V_PROPERTY(CWidget, std::string, click, getClick, setClick))
public:
  CWidget();

private:
  std::string render;
  std::string click;

public:
  void renderObject(std::shared_ptr<CGui> reneder,
                    std::shared_ptr<SDL_Rect> rect, int frameTime) override;

  bool mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type,
                  int button, int x, int y) override;

  std::string getClick();

  void setClick(std::string click);

  std::string getRender();

  void setRender(std::string draw);
};

// TODO: unify with CGameTextPanel
class CTextWidget : public CWidget {
  V_META(CTextWidget, CWidget,
         V_PROPERTY(CTextWidget, std::string, text, getText, setText),
         V_PROPERTY(CTextWidget, bool, centered, getCentered, setCentered))
public:
  void renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect,
                    int frameTime) override;

  bool getCentered() const;

  void setCentered(bool centered);

  const std::string &getText() const;

  void setText(const std::string &text);

private:
  bool centered = true;
  std::string text;
};

class CButton : public CTextWidget {
  V_META(CButton, CTextWidget, vstd::meta::empty())
public:
  CButton();

  bool mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type,
                  int button, int x, int y) override;
};