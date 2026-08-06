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

#include <cmath>

StatsModifier &StatsModifier::operator+=(const StatsModifier &other) {
    strength += other.strength;
    agility += other.agility;
    stamina += other.stamina;
    intelligence += other.intelligence;
    armor += other.armor;
    block += other.block;
    dmgMin += other.dmgMin;
    dmgMax += other.dmgMax;
    attack += other.attack;
    hit += other.hit;
    crit += other.crit;
    fireResist += other.fireResist;
    frostResist += other.frostResist;
    normalResist += other.normalResist;
    thunderResist += other.thunderResist;
    shadowResist += other.shadowResist;
    damage += other.damage;
    return *this;
}

StatsModifier &StatsModifier::operator-=(const StatsModifier &other) { return *this += -other; }

StatsModifier StatsModifier::operator-() const {
    return {
        .strength = -strength,
        .agility = -agility,
        .stamina = -stamina,
        .intelligence = -intelligence,
        .armor = -armor,
        .block = -block,
        .dmgMin = -dmgMin,
        .dmgMax = -dmgMax,
        .attack = -attack,
        .hit = -hit,
        .crit = -crit,
        .fireResist = -fireResist,
        .frostResist = -frostResist,
        .normalResist = -normalResist,
        .thunderResist = -thunderResist,
        .shadowResist = -shadowResist,
        .damage = -damage,
    };
}

DamageValue &DamageValue::operator+=(const DamageValue &other) {
    normal += other.normal;
    fire += other.fire;
    frost += other.frost;
    thunder += other.thunder;
    shadow += other.shadow;
    return *this;
}

DamageValue &DamageValue::operator-=(const DamageValue &other) { return *this += -other; }

DamageValue DamageValue::operator-() const {
    return {
        .normal = -normal,
        .fire = -fire,
        .frost = -frost,
        .thunder = -thunder,
        .shadow = -shadow,
    };
}

DamageValue &DamageValue::scale(double multiplier) {
    normal = static_cast<int>(std::lround(normal * multiplier));
    fire = static_cast<int>(std::lround(fire * multiplier));
    frost = static_cast<int>(std::lround(frost * multiplier));
    thunder = static_cast<int>(std::lround(thunder * multiplier));
    shadow = static_cast<int>(std::lround(shadow * multiplier));
    return *this;
}

DamageValue DamageValue::scaled(double multiplier) const {
    auto result = *this;
    return result.scale(multiplier);
}

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

StatsModifier CStats::modifier() const {
    return {
        .strength = strength,
        .agility = agility,
        .stamina = stamina,
        .intelligence = intelligence,
        .armor = armor,
        .block = block,
        .dmgMin = dmgMin,
        .dmgMax = dmgMax,
        .attack = attack,
        .hit = hit,
        .crit = crit,
        .fireResist = fireResist,
        .frostResist = frostResist,
        .normalResist = normalResist,
        .thunderResist = thunderResist,
        .shadowResist = shadowResist,
        .damage = damage,
    };
}

CStats &CStats::apply(const StatsModifier &value) {
    incProperty("strength", value.strength);
    incProperty("agility", value.agility);
    incProperty("stamina", value.stamina);
    incProperty("intelligence", value.intelligence);
    incProperty("armor", value.armor);
    incProperty("block", value.block);
    incProperty("dmgMin", value.dmgMin);
    incProperty("dmgMax", value.dmgMax);
    incProperty("attack", value.attack);
    incProperty("hit", value.hit);
    incProperty("crit", value.crit);
    incProperty("fireResist", value.fireResist);
    incProperty("frostResist", value.frostResist);
    incProperty("normalResist", value.normalResist);
    incProperty("thunderResist", value.thunderResist);
    incProperty("shadowResist", value.shadowResist);
    incProperty("damage", value.damage);
    return *this;
}

CStats &CStats::operator+=(const CStats &other) { return apply(other.modifier()); }

CStats &CStats::operator-=(const CStats &other) { return apply(-other.modifier()); }

void CStats::addBonus(std::shared_ptr<CStats> stats) { *this += *stats; }

void CStats::removeBonus(std::shared_ptr<CStats> stats) { *this -= *stats; }

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

DamageValue CDamage::value() const {
    return {
        .normal = normal,
        .fire = fire,
        .frost = frost,
        .thunder = thunder,
        .shadow = shadow,
    };
}

CDamage &CDamage::apply(const DamageValue &value) {
    incProperty("normal", value.normal);
    incProperty("fire", value.fire);
    incProperty("frost", value.frost);
    incProperty("thunder", value.thunder);
    incProperty("shadow", value.shadow);
    return *this;
}

CDamage &CDamage::operator+=(const CDamage &other) { return apply(other.value()); }

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
