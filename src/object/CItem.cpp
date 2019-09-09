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
#include "CItem.h"
#include "core/CGame.h"
#include "core/CMap.h"
CItem::CItem() {
}

CItem::~CItem() {

}

void CItem::onEnter(std::shared_ptr<CGameEvent> event) {
    if (std::shared_ptr<CCreature> visitor = vstd::cast<CCreature>(vstd::cast<CGameEventCaused>(event)->getCause())) {
        this->getMap()->removeObject(this->ptr<CMapObject>());
        visitor->addItem(this->ptr<CItem>());
    }
}

void CItem::onLeave(std::shared_ptr<CGameEvent>) {

}

void CItem::onEquip(std::shared_ptr<CGameEvent> event) {
    vstd::cast<CCreature>(vstd::cast<CGameEventCaused>(event)->getCause())->addBonus(bonus);
    vstd::logger::debug(vstd::cast<CGameEventCaused>(event)->getCause()->getType(), "equipped", getType(), "\n");
}

void CItem::onUnequip(std::shared_ptr<CGameEvent> event) {
    vstd::cast<CCreature>(vstd::cast<CGameEventCaused>(event)->getCause())->removeBonus(bonus);
    vstd::logger::debug(vstd::cast<CGameEventCaused>(event)->getCause()->getType(), "unequipped", getType(),
                        "\n");
}

void CItem::onUse(std::shared_ptr<CGameEvent> event) {

}

int CItem::getPower() const {
    return power;
}

void CItem::setPower(int value) {
    power = value;
}

CArmor::CArmor() {

}

std::shared_ptr<CInteraction> CItem::getInteraction() {
    return interaction;
}

void CItem::setInteraction(std::shared_ptr<CInteraction> interaction) {
    this->interaction = interaction;
    interaction->setManaCost(0);
}

CBelt::CBelt() {

}

CBoots::CBoots() {

}

CGloves::CGloves() {

}

CHelmet::CHelmet() {

}

CSmallWeapon::CSmallWeapon() {

}

CWeapon::CWeapon() : CItem() {

}

std::shared_ptr<Stats> CItem::getBonus() {
    return bonus;
}

void CItem::setBonus(std::shared_ptr<Stats> stats) {
    bonus = stats;
}

bool CItem::isDisposable() {
    return false;
}

CPotion::CPotion() {

}

bool CPotion::isDisposable() {
    return true;
}

CScroll::CScroll() {

}

std::string CScroll::getText() const {
    return text;
}

void CScroll::setText(const std::string &value) {
    text = value;
}

void CScroll::onUse(std::shared_ptr<CGameEvent>) {
    getMap()->getGame()->getGuiHandler()->showMessage(text);
}

