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
#include "CInteraction.h"
#include "core/CGame.h"

CInteraction::CInteraction() {}

CInteraction::~CInteraction() {}

void CInteraction::onAction(std::shared_ptr<CCreature> first,
                            std::shared_ptr<CCreature> second) {
  vstd::logger::debug(first->to_string(), "used", this->to_string(), "against",
                      second->to_string());

  first->takeMana(this->getManaCost());

  this->performAction(first, second);

  if (effect) {
    std::shared_ptr<CEffect> effect = this->effect->clone<CEffect>();
    effect->setCaster(first);
    if (this->configureEffect(effect)) {
      if (effect->getAnimation().empty()) {
        effect->setAnimation(getAnimation());
      }
      if (effect->getLabel().empty()) {
        effect->setLabel(getLabel());
      }
      if (effect->hasTag("buff")) {
        effect->setVictim(first);
        first->addEffect(effect);
      } else {
        effect->setVictim(second);
        second->addEffect(effect);
      }
    }
  }
}

int CInteraction::getManaCost() const { return manaCost; }

void CInteraction::setManaCost(int value) { manaCost = value; }

std::shared_ptr<CEffect> CInteraction::getEffect() const { return effect; }

void CInteraction::setEffect(const std::shared_ptr<CEffect> value) {
  effect = value;
}

void CInteraction::performAction(std::shared_ptr<CCreature>,
                                 std::shared_ptr<CCreature>) {}

bool CInteraction::configureEffect(std::shared_ptr<CEffect>) { return true; }
