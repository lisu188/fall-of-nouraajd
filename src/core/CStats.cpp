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
#include "core/CStats.h"

int CStats::getAttack() const { return attack; }

void CStats::setAttack(int value) { attack = value; }

int CStats::getDamage() const { return damage; }

void CStats::setDamage(int value) { damage = value; }

int CStats::getShadowResist() const { return shadowResist; }

void CStats::setShadowResist(int value) { shadowResist = value; }

int CStats::getThunderResist() const { return thunderResist; }

void CStats::setThunderResist(int value) { thunderResist = value; }

int CStats::getNormalResist() const { return normalResist; }

void CStats::setNormalResist(int value) { normalResist = value; }

int CStats::getFrostResist() const { return frostResist; }

void CStats::setFrostResist(int value) { frostResist = value; }

int CStats::getFireResist() const { return fireResist; }

void CStats::setFireResist(int value) { fireResist = value; }

int CStats::getCrit() const { return crit; }

void CStats::setCrit(int value) { crit = value; }

int CStats::getHit() const { return hit; }

void CStats::setHit(int value) { hit = value; }

int CStats::getDmgMax() const { return dmgMax; }

void CStats::setDmgMax(int value) { dmgMax = value; }

int CStats::getDmgMin() const { return dmgMin; }

void CStats::setDmgMin(int value) { dmgMin = value; }

int CStats::getBlock() const { return block; }

void CStats::setBlock(int value) { block = value; }

int CStats::getArmor() const { return armor; }

void CStats::setArmor(int value) { armor = value; }

int CStats::getIntelligence() const { return intelligence; }

void CStats::setIntelligence(int value) { intelligence = value; }

int CStats::getStamina() const { return stamina; }

void CStats::setStamina(int value) { stamina = value; }

int CStats::getAgility() const { return agility; }

void CStats::setAgility(int value) { agility = value; }

int CStats::getStrength() const { return strength; }

void CStats::setStrength(int value) { strength = value; }

std::string CStats::getMainStat() const { return mainStat; }

void CStats::setMainStat(const std::string &value) { mainStat = value; }

int CStats::getMainValue() { return this->getNumericProperty(mainStat); }

CStats::CStats() {}

void CStats::addBonus(std::shared_ptr<CStats> stats) {
    stats->meta()->for_all_properties(stats, [&](auto property) {
        if (property->value_type() == std::type_index(typeid(int))) {
            this->incProperty(property->name(), stats->getProperty<int>(property->name()));
        }
    });
}

void CStats::removeBonus(std::shared_ptr<CStats> stats) {
    stats->meta()->for_all_properties(stats, [&](auto property) {
        if (property->value_type() == std::type_index(typeid(int))) {
            this->incProperty(property->name(), -stats->getProperty<int>(property->name()));
        }
    });
}

std::string CStats::getText(int level) {
    std::ostringstream stream;
    stream << "Level: " << level << "\n";
    stream << "Strength: " << strength << "\n";
    stream << "Agility: " << agility << "\n";
    stream << "Intelligence: " << intelligence << "\n";
    stream << "Stamina: " << stamina << "\n";
    stream << "Damage: " << dmgMin + damage << "-" << dmgMax + damage << "\n";
    stream << "Hit: " << hit + attack << "%" << "\n";
    stream << "Crit: " << crit << "%" << "\n";
    stream << "Armor: " << armor << "%" << "\n";
    stream << "Block: " << block << "%" << "\n";
    return stream.str();
}

CDamage::CDamage() {}

int CDamage::getFire() const { return fire; }

void CDamage::setFire(int value) { fire = value; }

int CDamage::getFrost() const { return frost; }

void CDamage::setFrost(int value) { frost = value; }

int CDamage::getThunder() const { return thunder; }

void CDamage::setThunder(int value) { thunder = value; }

int CDamage::getShadow() const { return shadow; }

void CDamage::setShadow(int value) { shadow = value; }

int CDamage::getNormal() const { return normal; }

void CDamage::setNormal(int value) { normal = value; }
