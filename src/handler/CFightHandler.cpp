#include "CFightHandler.h"
#include "object/CCreature.h"
#include "object/CInteraction.h"
#include "core/CController.h"
#include "core/CTags.h"

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
    std::set<std::shared_ptr<CItem>> items = b->getMap()->getLootHandler()->getLoot(b->getScale());
    for (std::shared_ptr<CItem> item:b->getInInventory()) {
        b->removeFromInventory(item);
        items.insert(item);
    }
    a->addItem(items);
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