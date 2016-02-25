#include "CFightHandler.h"
#include "object/CCreature.h"
#include "object/CInteraction.h"
#include "core/CController.h"


void static CFightHandler::fight(std::shared_ptr<CCreature> a, std::shared_ptr<CCreature> b) {
    int draw = 5;
    while (a->isAlive() && b->isAlive() && draw > 0) {
        if (a->applyEffects()) {
            continue;
        }
        if (!a->isAlive()) {
            defeatedCreature(b, a);
            continue;
        }
        if (a->getFightController()->control(a, b)) {
            draw = 5;
        }
        std::shared_ptr<CInteraction> action = a->selectAction();
        if (action) {
            action->onAction(a, b);
            if (b->getArmor()) {
                if (b->getArmor()->getInteraction()) {
                    b->getArmor()->getInteraction()->onAction(b, a);
                }
            }
        }
        a.swap(b);
        draw--;
    }

}

void static CFightHandler::defeatedCreature(std::shared_ptr<CCreature> a, std::shared_ptr<CCreature> b) {
    vstd::logger::debug(a->to_string(), a->getName(), "defeated", b->to_string());
    a->addExpScaled(b->getScale());
    //TODO: loot handler
    a->addItem(b->getLoot());
    a->getMap()->removeObject(b);
}