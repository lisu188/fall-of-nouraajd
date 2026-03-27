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
#include "CFightHandler.h"
#include "core/CController.h"
#include "core/CGame.h"
#include "core/CMap.h"
#include "core/CTags.h"
#include "object/CCreature.h"

bool CFightHandler::fight(std::shared_ptr<CCreature> a,
                          std::shared_ptr<CCreature> b) {
  bool retVal = false;
  a->getFightController()->start(a, b);
  b->getFightController()->start(b, a);

  auto state = [](const std::shared_ptr<CCreature> &creature) {
    return std::make_tuple(creature->getHp(), creature->getMana(),
                           creature->getEffects().size(),
                           creature->getInInventory().size());
  };

  int stale_turns = 0;
  for (int turn = 0; turn < 100 && stale_turns < 20; ++turn) {
    auto before = std::make_pair(state(a), state(b));
    applyEffects(a);
    if (!a->isAlive()) {
      // TODO: who was the caster? we should gratify him
      defeatedCreature(b, a);
      retVal = true;
      break;
    }
    if (!CTags::isTagPresent(a->getEffects(), "stun")) {
      a->getFightController()->control(a, b);
      if (!b->isAlive()) {
        defeatedCreature(a, b);
        retVal = true;
        break;
      }
    }
    auto after = std::make_pair(state(a), state(b));
    stale_turns = after == before ? stale_turns + 1 : 0;
    a.swap(b);
  }

  a->getFightController()->end(a, b);
  b->getFightController()->end(b, a);

  return retVal;
}

void CFightHandler::defeatedCreature(const std::shared_ptr<CCreature> &a,
                                     const std::shared_ptr<CCreature> &b) {
  vstd::logger::debug(a->to_string(), a->getName(), "defeated", b->to_string());
  a->addExpScaled(b->getScale());
  // TODO: loot handler
  std::set<std::shared_ptr<CItem>> items =
      b->getGame()->getRngHandler()->getRandomLoot(b->getScale());
  for (const std::shared_ptr<CItem> &item : b->getInInventory()) {
    if (!b->isPlayer() || !item->hasTag("quest")) {
      b->removeItem(item);
      items.insert(item);
    }
  }
  a->getGame()->getRngHandler()->addRandomLoot(a, items);
  a->getMap()->removeObject(b);
}

void CFightHandler::applyEffects(const std::shared_ptr<CCreature> &cr) {
  auto effects = cr->getEffects();

  for (const auto &effect : effects) {
    if (effect->getTimeLeft() == 0) {
      vstd::logger::debug(cr->to_string(), "is now free from",
                          effect->to_string());
      cr->removeEffect(effect);
      applyEffects(cr);
      return;
    }
  }
  for (const auto &effect : effects) {
    vstd::logger::debug(cr->to_string(), "suffers from", effect->to_string());
    effect->apply(cr);
    if (!cr->isAlive()) {
      break;
    }
  }
}
