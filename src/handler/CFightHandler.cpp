#include "CFightHandler.h"
#include "object/CCreature.h"
#include "object/CInteraction.h"
#include "core/CController.h"
#include "core/CTags.h"

void CFightHandler::fight(std::shared_ptr <CCreature> a, std::shared_ptr <CCreature> b) {
    //TODO: this is mess!
    int draw = 5;
    while (a->isAlive() && b->isAlive() && draw > 0) {
        applyEffects(a);
        if (!a->isAlive()) {
            defeatedCreature(b, a);
            continue;
        }
        if (!CTags::isTagPresent(a->getEffects(), "stun")) {
            if (a->getFightController()->control(a, b)) {
                draw = 5;
            }
            if (!b->isAlive()) {
                defeatedCreature(a, b);
                continue;
            }
        }
        a.swap(b);
        draw--;
    }

}

void CFightHandler::defeatedCreature(std::shared_ptr <CCreature> a, std::shared_ptr <CCreature> b) {
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

void CFightHandler::applyEffects(std::shared_ptr <CCreature> cr) {
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