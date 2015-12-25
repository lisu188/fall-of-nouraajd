#include "CMapObject.h"
#include "core/CMap.h"
#include "core/CGame.h"

CMapObject::CMapObject() {

}

CMapObject::~CMapObject() {

}

void CMapObject::move ( int x, int y, int z ) {
    if ( dynamic_cast<Moveable *> ( this ) ) {
        if ( !getMap()->getTile ( posx + x, posy + y, posz )->canStep() ) {
            return;
        }
        dynamic_cast<Moveable *> ( this )->beforeMove();
    }

    posx += x;
    posy += y;
    posz += z;
    setPos ( posx * 50, posy * 50 );

    if ( dynamic_cast<Moveable *> ( this ) ) {
        dynamic_cast<Moveable *> ( this )->afterMove();
    }
}

void CMapObject::move ( Coords coords ) {
    this->move ( coords.x, coords.y, coords.z );
}

void CMapObject::moveTo ( int x, int y, int z ) {
    move ( x - posx, y - posy, z - posz );
}

void CMapObject::moveTo ( Coords coords ) {
    this->moveTo ( coords.x, coords.y, coords.z );
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

void CMapObject::onTurn ( std::shared_ptr<CGameEvent> ) {

}

void CMapObject::onCreate ( std::shared_ptr<CGameEvent> ) {

}

void CMapObject::onDestroy ( std::shared_ptr<CGameEvent> ) {

}

Coords CMapObject::getCoords() {
    return Coords ( posx, posy, posz );
}

void CMapObject::setCoords ( Coords coords ) {
    this->moveTo ( coords.x, coords.y, coords.z );
}
