#include "CTile.h"
#include "core/CGame.h"

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