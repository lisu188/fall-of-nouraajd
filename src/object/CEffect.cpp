#include "CEffect.h"
#include "CCreature.h"

CEffect::CEffect() {

}

CEffect::~CEffect() {

}

int CEffect::getTimeLeft() {
    return timeLeft;
}

int CEffect::getTimeTotal() {
    return timeTotal;
}

std::shared_ptr<CCreature> CEffect::getCaster() {
    return caster;
}

std::shared_ptr<CCreature> CEffect::getVictim() {
    return victim;
}

bool CEffect::apply(std::shared_ptr<CCreature> creature) {
    if (bonus) {
        if (timeTotal == timeLeft) {
            creature->addBonus(bonus);
        }
    }
    timeLeft--;
    if (timeLeft == 0) {
        if (bonus) {
            creature->removeBonus(bonus);
        }
        return false;
    }
    return onEffect();
}

std::shared_ptr<Stats> CEffect::getBonus() {
    return bonus;
}

void CEffect::setBonus(std::shared_ptr<Stats> value) {
    bonus = value;
}

int CEffect::getDuration() {
    return duration;
}

void CEffect::setDuration(int duration) {
    this->duration = duration;
    timeLeft = timeTotal = duration;
}

bool CEffect::onEffect() {
    return false;
}

void CEffect::setCaster(std::shared_ptr<CCreature> value) {
    caster = value;
}

void CEffect::setVictim(std::shared_ptr<CCreature> value) {
    victim = value;
}

void CEffect::setCumulative(bool value) {
    this->cumulative = value;
}

bool CEffect::getCumulative() {
    return this->cumulative;
}