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

#include "CGameGraphicsObject.h"

class CScript;

class CCreature;

// TODO: move from here
class CStatsGraphicsUtil {
public:
  static void drawStats(std::shared_ptr<CGui> gui,
                        std::shared_ptr<CCreature> creature, int x, int y,
                        int h, int w, bool showNumeric, bool showExp);

private:
  static void drawBar(std::shared_ptr<CGui> gui, int ratio, int index, Uint8 r,
                      Uint8 g, Uint8 b, Uint8 a, int x, int y, int h, int w);

  static void drawValues(std::shared_ptr<CGui> gui, int left, int right,
                         int index, int x, int y, int h, int w);
};

class CStatsGraphicsObject : public CGameGraphicsObject {
  V_META(CStatsGraphicsObject, CGameGraphicsObject,
         V_PROPERTY(CStatsGraphicsObject, std::shared_ptr<CScript>, creature,
                    getCreature, setCreature))
public:
  CStatsGraphicsObject();

  void renderObject(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> rect,
                    int frameTime) override;

  std::shared_ptr<CScript> getCreature();

  void setCreature(std::shared_ptr<CScript> _creature);

  bool mouseEvent(std::shared_ptr<CGui> sharedPtr, SDL_EventType type,
                  int button, int x, int y) override;

private:
  std::shared_ptr<CScript> creature;
};