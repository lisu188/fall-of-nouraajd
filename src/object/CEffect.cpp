//fall-of-nouraajd c++ dark fantasy game
//Copyright (C) 2019  Andrzej Lis
//
//This program is free software: you can redistribute it and/or modify
//        it under the terms of the GNU General Public License as published by
//the Free Software Foundation, either version 3 of the License, or
//(at your option) any later version.
//
//This program is distributed in the hope that it will be useful,
//        but WITHOUT ANY WARRANTY; without even the implied warranty of
//MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//GNU General Public License for more details.
//
//You should have received a copy of the GNU General Public License
//along with this program.  If not, see <https://www.gnu.org/licenses/>.
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

void CEffect::apply(std::shared_ptr<CCreature> creature) {
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
    } else {
        onEffect();
    }
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

void CEffect::onEffect() {

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