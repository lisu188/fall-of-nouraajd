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
#include "CTile.h"
#include "core/CGame.h"
#include "core/CMap.h"
CTile::CTile() {
}

CTile::~CTile() {

}

void CTile::move(int x, int y, int z) {
    if (getMap()) {
        getMap()->moveTile(this->ptr<CTile>(), posx + x, posy + y, posz + z);
        setXYZ(posx + x, posy + y, posz + z);
    }
}

void CTile::moveTo(int x, int y, int z) {
    move(x - posx, y - posy, z - posz);
}

Coords CTile::getCoords() {
    return Coords(posx, posy, posz);
}

void CTile::onStep(std::shared_ptr<CCreature>) {

}

bool CTile::canStep() const {
    return step;
}

void CTile::setCanStep(bool canStep) {
    this->step = canStep;
}

int CTile::getPosx() const {
    return posx;
}

void CTile::setPosx(int value) {
    posx = value;
}

int CTile::getPosy() const {
    return posy;
}

void CTile::setPosy(int value) {
    posy = value;
}

int CTile::getPosz() const {
    return posz;
}

void CTile::setPosz(int value) {
    posz = value;
}

void CTile::setXYZ(int x, int y, int z) {
    posx = x;
    posy = y;
    posz = z;
}

const std::string &CTile::getTileType() const {
    return tileType;
}

void CTile::setTileType(const std::string &tileType) {
    CTile::tileType = tileType;
}