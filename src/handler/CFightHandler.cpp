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
#include "CFightHandler.h"
#include "object/CCreature.h"
#include "object/CInteraction.h"
#include "core/CController.h"
#include "core/CTags.h"
#include "core/CGame.h"
#include "core/CMap.h"

bool CFightHandler::fight(std::shared_ptr<CCreature> a, std::shared_ptr<CCreature> b) {
    bool retVal = false;
    a->getFightController()->start(a, b);
    b->getFightController()->start(b, a);

    //TODO: this is mess!
    for (int i = 0; i < 5; i++) {//TODO: max number of turns? do we need it? implement draw.
        applyEffects(a);
        if (!a->isAlive()) {
            //TODO: who was the caster? we should gratify him
            defeatedCreature(b, a);
            retVal = true;
            break;
        }
        if (!CTags::isTagPresent(a->getEffects(), "stun")) {
            if (a->getFightController()->control(a, b)) {
                i = 0;
            }
            if (!b->isAlive()) {
                defeatedCreature(a, b);
                retVal = true;
                break;
            }
        }
        a.swap(b);
    }

    a->getFightController()->end(a, b);
    b->getFightController()->end(b, a);

    return retVal;
}

void CFightHandler::defeatedCreature(std::shared_ptr<CCreature> a, std::shared_ptr<CCreature> b) {
    vstd::logger::debug(a->to_string(), a->getName(), "defeated", b->to_string());
    a->addExpScaled(b->getScale());
    //TODO: loot handler
    std::set<std::shared_ptr<CItem>> items = b->getGame()->getLootHandler()->getLoot(b->getScale());
    for (const std::shared_ptr<CItem> &item:b->getInInventory()) {
        //TODO: this check should be more polymorphic
        if (!vstd::castable<CPlayer>(b) || !item->hasTag("quest")) {
            b->removeItem(item);
            items.insert(item);
        }
    }
    a->getGame()->getGuiHandler()->showLoot(a, items);
    a->getMap()->removeObject(b);
}

void CFightHandler::applyEffects(std::shared_ptr<CCreature> cr) {
    auto effects = cr->getEffects();

    for (auto it = effects.begin(); it != effects.end(); it++) {
        if ((*it)->getTimeLeft() == 0) {
            vstd::logger::debug(cr->to_string(), "is now free from", (*it)->to_string());
            cr->removeEffect(*it);
            applyEffects(cr);
            return;
        }
    }
    for (std::shared_ptr<CEffect> effect:effects) {
        vstd::logger::debug(cr->to_string(), "suffers from", effect->to_string());
        effect->apply(cr);
        if (!cr->isAlive()) {
            break;
        }
    }
}