#include "CTile.h"
#include "CGame.h"
#include "CMap.h"

CTile::CTile() {
    this->setZValue ( 0 );
    this->hasTooltip=false;
}

CTile::~CTile() {

}

void CTile::move ( int x, int y, int z ) {
    if (  getMap() ) {
        getMap()->moveTile ( this,posx+x,posy+y, posz+z );
        setXYZ ( posx+x,posy+y, posz+z );
    }
}

void CTile::moveTo ( int x, int y, int z ) {
    move ( x - posx, y - posy ,z-posz );
}

Coords CTile::getCoords() {
    return Coords ( posx, posy, posz );
}

void CTile::onStep ( CCreature * ) {

}

bool CTile::canStep() const {
    return step;
}

void CTile::setCanStep ( bool canStep ) {
    this->step=canStep;
}

void CTile::addToScene ( CGame *scene ) {
    if ( scene ) {
        scene->addItem ( this );
    }
    setXYZ (  posx , posy,posz );
}

void CTile::removeFromScene ( CGame *scene ) {
    if ( scene ) {
        scene->removeItem ( this );
    }
}

void CTile::setXYZ ( int x, int y, int z ) {
    posx = x;
    posy = y;
    posz = z;
    setPos ( x*50,y*50 );
}
