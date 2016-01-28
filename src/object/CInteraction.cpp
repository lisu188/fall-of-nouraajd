#include "CInteraction.h"
#include "core/CGame.h"

CInteraction::CInteraction() {
}

CInteraction::~CInteraction() {

}

void CInteraction::onAction(std::shared_ptr<CCreature> first, std::shared_ptr<CCreature> second) {
    vstd::logger::debug(first->to_string(), "used", this->to_string(), "against", second->to_string());

    first->takeMana(this->getManaCost());

    this->performAction(first, second);

    if (effect) {
        std::shared_ptr<CEffect> effect = getMap()->getObjectHandler()->clone(this->effect);
        effect->setCaster(first);
        if (this->configureEffect(effect)) {
            std::shared_ptr<CCreature> victim;
            if (effect->isBuff()) {
                victim = first;
            } else {
                victim = second;
            }
            effect->setVictim(victim);
            victim->addEffect(effect);
        }
    }
}

int CInteraction::getManaCost() const {
    return manaCost;
}

void CInteraction::setManaCost(int value) {
    manaCost = value;
}

std::shared_ptr<CEffect> CInteraction::getEffect() const {
    return effect;
}

void CInteraction::setEffect(const std::shared_ptr<CEffect> value) {
    effect = value;
}

void CInteraction::performAction(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>) {

}

bool CInteraction::configureEffect(std::shared_ptr<CEffect>) {
    return true;
}
