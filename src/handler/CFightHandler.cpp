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
#include <algorithm>
#include <unordered_set>

#include "core/CController.h"
#include "core/CGame.h"
#include "core/CMap.h"
#include "core/CTags.h"
#include "object/CCreature.h"

namespace {
using encounter_type = std::vector<std::shared_ptr<CCreature>>;

auto creature_state(const std::shared_ptr<CCreature> &creature) {
  return std::make_tuple(creature->getName(), creature->getHp(),
                         creature->getMana(), creature->getEffects().size(),
                         creature->getInInventory().size());
}

auto encounter_state(const std::shared_ptr<CCreature> &attacker,
                     const encounter_type &opponents) {
  std::vector<decltype(creature_state(attacker))> state;
  state.push_back(creature_state(attacker));
  for (const auto &opponent : opponents) {
    state.push_back(creature_state(opponent));
  }
  return state;
}

bool is_present(const std::shared_ptr<CCreature> &creature) {
  return creature && creature->getMap() &&
         creature->getMap()->getObjectByName(creature->getName());
}

encounter_type sanitize_opponents(const std::shared_ptr<CCreature> &attacker,
                                  const encounter_type &opponents) {
  if (!attacker || !attacker->isAlive() || !is_present(attacker)) {
    return {};
  }

  encounter_type living;
  std::unordered_set<std::string> names;
  for (const auto &candidate : opponents) {
    if (!candidate || candidate == attacker || !candidate->isAlive() ||
        !is_present(candidate)) {
      continue;
    }
    if (names.insert(candidate->getName()).second) {
      living.push_back(candidate);
    }
  }
  std::sort(living.begin(), living.end(),
            [](const auto &left, const auto &right) {
              return left->getName() < right->getName();
            });
  return living;
}

std::shared_ptr<CCreature>
resolve_target(const std::shared_ptr<CCreature> &attacker,
               const encounter_type &opponents,
               std::shared_ptr<CCreature> current) {
  auto controller = attacker->getFightController();
  controller->setOpponents(attacker, opponents);
  auto selected = controller->selectOpponent(attacker, opponents, current);
  return selected ? selected
                  : (opponents.empty() ? std::shared_ptr<CCreature>()
                                       : opponents.front());
}

bool remove_dead_opponents(const std::shared_ptr<CCreature> &winner,
                           encounter_type &opponents) {
  bool changed = false;
  const bool reward_winner =
      winner && winner->isAlive() && is_present(winner);
  opponents.erase(
      std::remove_if(opponents.begin(), opponents.end(),
                     [&](const auto &opponent) {
                       if (!opponent || !is_present(opponent)) {
                         changed = true;
                         return true;
                       }
                       if (opponent->isAlive()) {
                         return false;
                       }
                       changed = true;
                       if (reward_winner) {
                         CFightHandler::defeatedCreature(winner, opponent);
                       } else if (is_present(opponent)) {
                         opponent->getMap()->removeObject(opponent);
                       }
                       return true;
                     }),
      opponents.end());
  return changed;
}

void defeat_attacker(const std::shared_ptr<CCreature> &attacker,
                     const encounter_type &opponents,
                     const std::shared_ptr<CCreature> &preferredWinner) {
  auto winner = preferredWinner;
  if (!winner || !winner->isAlive() || !is_present(winner) ||
      std::find(opponents.begin(), opponents.end(), winner) ==
          opponents.end()) {
    winner = opponents.empty() ? std::shared_ptr<CCreature>()
                               : opponents.front();
  }
  if (winner) {
    CFightHandler::defeatedCreature(winner, attacker);
  } else if (is_present(attacker)) {
    attacker->getMap()->removeObject(attacker);
  }
}

} // namespace

bool CFightHandler::fight(std::shared_ptr<CCreature> a,
                          std::shared_ptr<CCreature> b) {
  return fightMany(a, {b});
}

bool CFightHandler::fightMany(
    std::shared_ptr<CCreature> attacker,
    const std::vector<std::shared_ptr<CCreature>> &encounterOpponents) {
  auto opponents = sanitize_opponents(attacker, encounterOpponents);
  if (opponents.empty()) {
    return false;
  }

  auto allOpponents = opponents;
  auto current = opponents.front();
  attacker->getFightController()->setOpponents(attacker, opponents);
  attacker->getFightController()->start(attacker, current);
  for (const auto &opponent : allOpponents) {
    opponent->getFightController()->start(opponent, attacker);
  }

  int stale_turns = 0;
  bool resolved = false;
  for (int turn = 0;
       turn < 100 && stale_turns < 20 && attacker->isAlive() &&
       !opponents.empty();
       ++turn) {
    current = resolve_target(attacker, opponents, current);
    auto before = encounter_state(attacker, opponents);

    applyEffects(attacker);
    if (!attacker->isAlive()) {
      // TODO: who was the caster? we should gratify him
      defeat_attacker(attacker, opponents, current);
      resolved = true;
      break;
    }

    if (!CTags::isTagPresent(attacker->getEffects(), CTag::Stun)) {
      attacker->getFightController()->control(attacker, current);
      remove_dead_opponents(attacker, opponents);
      if (!attacker->isAlive()) {
        defeat_attacker(attacker, opponents, current);
        resolved = true;
        break;
      }
      if (opponents.empty()) {
        resolved = true;
        break;
      }
      current = resolve_target(attacker, opponents, current);
    }

    for (size_t i = 0; i < opponents.size() && attacker->isAlive();) {
      auto opponent = opponents[i];
      if (!opponent || !is_present(opponent)) {
        opponents.erase(opponents.begin() + i);
        if (opponents.empty()) {
          resolved = true;
          break;
        }
        current = resolve_target(attacker, opponents, current);
        continue;
      }
      applyEffects(opponent);
      if (!opponent->isAlive()) {
        if (remove_dead_opponents(attacker, opponents)) {
          if (opponents.empty()) {
            resolved = true;
            break;
          }
          current = resolve_target(attacker, opponents, current);
        }
        continue;
      }
      if (!CTags::isTagPresent(opponent->getEffects(), CTag::Stun)) {
        opponent->getFightController()->control(opponent, attacker);
        if (!attacker->isAlive()) {
          remove_dead_opponents(attacker, opponents);
          defeat_attacker(attacker, opponents, opponent);
          resolved = true;
          break;
        }
      }
      if (remove_dead_opponents(attacker, opponents)) {
        if (opponents.empty()) {
          resolved = true;
          break;
        }
        current = resolve_target(attacker, opponents, current);
        continue;
      }
      ++i;
    }

    if (resolved || !attacker->isAlive()) {
      break;
    }
    if (opponents.empty()) {
      resolved = true;
      break;
    }

    auto after = encounter_state(attacker, opponents);
    stale_turns = after == before ? stale_turns + 1 : 0;
  }

  attacker->getFightController()->end(attacker, current);
  for (const auto &opponent : allOpponents) {
    opponent->getFightController()->end(opponent, attacker);
  }

  return resolved;
}

void CFightHandler::defeatedCreature(const std::shared_ptr<CCreature> &a,
                                     const std::shared_ptr<CCreature> &b) {
  if (!a || !b || !is_present(b)) {
    return;
  }
  vstd::logger::debug(a->to_string(), a->getName(), "defeated", b->to_string());
  a->addExpScaled(b->getScale());
  // TODO: loot handler
  std::set<std::shared_ptr<CItem>> items =
      b->getGame()->getRngHandler()->getRandomLoot(b->getScale());
  for (const std::shared_ptr<CItem> &item : b->getInInventory()) {
    if (!b->isPlayer() || !item->hasTag(CTag::Quest)) {
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
