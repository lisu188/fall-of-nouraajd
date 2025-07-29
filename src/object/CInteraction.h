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

#include "core/CGlobal.h"
#include "object/CGameObject.h"

class CCreature;

class Stats;

class CEffect;

class CInteraction : public CGameObject {

  V_META(CInteraction, CGameObject,
         V_PROPERTY(CInteraction, std::shared_ptr<CEffect>, effect, getEffect,
                    setEffect),
         V_PROPERTY(CInteraction, int, manaCost, getManaCost, setManaCost))

public:
  CInteraction();

  ~CInteraction();

  void onAction(std::shared_ptr<CCreature> first,
                std::shared_ptr<CCreature> second);

  virtual void performAction(std::shared_ptr<CCreature>,
                             std::shared_ptr<CCreature>);

  virtual bool configureEffect(std::shared_ptr<CEffect>);

  std::shared_ptr<CEffect> getEffect() const;

  void setEffect(const std::shared_ptr<CEffect> value);

  int getManaCost() const;

  void setManaCost(int value);

private:
  int manaCost = 0;
  std::shared_ptr<CEffect> effect;
};
