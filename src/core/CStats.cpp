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
#include "core/CStats.h"

int Stats::getAttack() const {
    return attack;
}

void Stats::setAttack(int value) {
    attack = value;
}

int Stats::getDamage() const {
    return damage;
}

void Stats::setDamage(int value) {
    damage = value;
}

int Stats::getShadowResist() const {
    return shadowResist;
}

void Stats::setShadowResist(int value) {
    shadowResist = value;
}

int Stats::getThunderResist() const {
    return thunderResist;
}

void Stats::setThunderResist(int value) {
    thunderResist = value;
}

int Stats::getNormalResist() const {
    return normalResist;
}

void Stats::setNormalResist(int value) {
    normalResist = value;
}

int Stats::getFrostResist() const {
    return frostResist;
}

void Stats::setFrostResist(int value) {
    frostResist = value;
}

int Stats::getFireResist() const {
    return fireResist;
}

void Stats::setFireResist(int value) {
    fireResist = value;
}

int Stats::getCrit() const {
    return crit;
}

void Stats::setCrit(int value) {
    crit = value;
}

int Stats::getHit() const {
    return hit;
}

void Stats::setHit(int value) {
    hit = value;
}

int Stats::getDmgMax() const {
    return dmgMax;
}

void Stats::setDmgMax(int value) {
    dmgMax = value;
}

int Stats::getDmgMin() const {
    return dmgMin;
}

void Stats::setDmgMin(int value) {
    dmgMin = value;
}

int Stats::getBlock() const {
    return block;
}

void Stats::setBlock(int value) {
    block = value;
}

int Stats::getArmor() const {
    return armor;
}

void Stats::setArmor(int value) {
    armor = value;
}

int Stats::getIntelligence() const {
    return intelligence;
}

void Stats::setIntelligence(int value) {
    intelligence = value;
}

int Stats::getStamina() const {
    return stamina;
}

void Stats::setStamina(int value) {
    stamina = value;
}

int Stats::getAgility() const {
    return agility;
}

void Stats::setAgility(int value) {
    agility = value;
}

int Stats::getStrength() const {
    return strength;
}

void Stats::setStrength(int value) {
    strength = value;
}

std::string Stats::getMainStat() const {
    return mainStat;
}

void Stats::setMainStat(const std::string &value) {
    mainStat = value;
}

int Stats::getMainValue() {
    return this->getNumericProperty(mainStat);
}

Stats::Stats() {

}

void Stats::addBonus(std::shared_ptr<Stats> stats) {
    auto properties = stats->meta()->properties(stats);
    for (auto property:*properties) {
        if (property->value_type() == boost::typeindex::type_id<int>()) {
            this->incProperty(property->name(), stats->getProperty<int>(property->name()));
        }
    }
}

void Stats::removeBonus(std::shared_ptr<Stats> stats) {
    auto properties = stats->meta()->properties(stats);
    for (auto property:*properties) {
        if (property->value_type() == boost::typeindex::type_id<int>()) {
            this->incProperty(property->name(), -stats->getProperty<int>(property->name()));
        }
    }
}

const char *Stats::getText(int level) {
    std::ostringstream stream;
    stream << "Level: " << level << "\n";
    stream << "Strength: " << strength << "\n";
    stream << "Agility: " << agility << "\n";
    stream << "Intelligence: " << intelligence << "\n";
    stream << "Stamina: " << stamina << "\n";
    stream << "Damage: " << dmgMin + damage << "-" << dmgMax + damage << "\n";
    stream << "Hit: " << hit + attack << "%"
            << "\n";
    stream << "Crit: " << crit << "%"
            << "\n";
    stream << "Armor: " << armor << "%"
            << "\n";
    stream << "Block: " << block << "%"
            << "\n";
    return stream.str().c_str();
}


Damage::Damage() {

}

int Damage::getFire() const {
    return fire;
}

void Damage::setFire(int value) {
    fire = value;
}

int Damage::getFrost() const {
    return frost;
}

void Damage::setFrost(int value) {
    frost = value;
}

int Damage::getThunder() const {
    return thunder;
}

void Damage::setThunder(int value) {
    thunder = value;
}

int Damage::getShadow() const {
    return shadow;
}

void Damage::setShadow(int value) {
    shadow = value;
}

int Damage::getNormal() const {
    return normal;
}

void Damage::setNormal(int value) {
    normal = value;
}





