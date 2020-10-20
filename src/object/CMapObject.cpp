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
#include "CMapObject.h"
#include "core/CMap.h"
#include "core/CGame.h"

CMapObject::CMapObject() {

}

CMapObject::~CMapObject() {

}

void CMapObject::move(int x, int y, int z) {
    if (dynamic_cast<Moveable *> ( this )) {
        if (getMap()->getTile(posx + x, posy + y, posz) && !getMap()->getTile(posx + x, posy + y, posz)->canStep()) {
            vstd::logger::debug(getName(), "cannot step on:", posx + x, posy + y, posz);
            return;
        }
        dynamic_cast<Moveable *> ( this )->beforeMove();
    }

    Coords oldCoords(posx, posy, posz);
    posx += x;
    posy += y;
    posz += z;
    Coords newCoords(posx, posy, posz);

    getMap()->objectMoved(this->ptr<CMapObject>(), oldCoords, newCoords);

    if (dynamic_cast<Moveable *> ( this )) {
        dynamic_cast<Moveable *> ( this )->afterMove();
    }
}

void CMapObject::move(Coords coords) {
    this->move(coords.x, coords.y, coords.z);
}

void CMapObject::moveTo(int x, int y, int z) {
    move(x - posx, y - posy, z - posz);
}

void CMapObject::moveTo(Coords coords) {
    this->moveTo(coords.x, coords.y, coords.z);
}

int CMapObject::getPosY() const {
    return posy;
}

int CMapObject::getPosZ() const {
    return posz;
}

int CMapObject::getPosX() const {
    return posx;
}

void CMapObject::onTurn(std::shared_ptr<CGameEvent>) {

}

void CMapObject::onCreate(std::shared_ptr<CGameEvent>) {

}

void CMapObject::onDestroy(std::shared_ptr<CGameEvent>) {

}

Coords CMapObject::getCoords() {
    return Coords(posx, posy, posz);
}

void CMapObject::setCoords(Coords coords) {
    this->moveTo(coords.x, coords.y, coords.z);
}

bool CMapObject::isAffiliatedWith(std::shared_ptr<CMapObject> object) {
    return !vstd::is_empty(this->getAffiliation())
           && !vstd::is_empty(object->getAffiliation())
           && this->getAffiliation() == object->getAffiliation();
}

void CMapObject::setPosX(int posx) {
    this->posx = posx;
}

std::string CMapObject::getAffiliation() {
    return affiliation;
}

void CMapObject::setAffiliation(const std::string &affiliation) {
    CMapObject::affiliation = affiliation;
}

void CMapObject::setPosY(int posy) {
    this->posy = posy;
}

void CMapObject::setPosZ(int posz) {
    this->posz = posz;
}

bool CMapObject::getCanStep() {
    return canStep;
}

void CMapObject::setCanStep(bool step) {
    canStep = step;
}
