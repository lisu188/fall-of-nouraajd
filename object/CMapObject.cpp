#include "CMapObject.h"
#include "CMap.h"
#include "CGameScene.h"
#include "CCreature.h"
#include "CTile.h"

CMapObject::CMapObject() {
	connect ( this,&CGameObject::mapChanged,this,&CMapObject::onMapChanged );
}

CMapObject::~CMapObject() {

}

void CMapObject::move ( int x, int y ,int z ) {
	if ( dynamic_cast<Moveable*> ( this ) ) {
		if ( !getMap()->getTile ( posx + x, posy + y, posz )->canStep() ) {
			return;
		}
		dynamic_cast<Moveable*> ( this ) ->beforeMove();
	}

	posx += x;
	posy += y;
	posz += z;
	setPos ( posx * 50, posy * 50 );

	if ( dynamic_cast<Moveable*> ( this ) ) {
		dynamic_cast<Moveable*> ( this ) ->afterMove();
	}
}

void CMapObject::move ( Coords coords ) {
	this->move ( coords.x,coords.y,coords.z );
}

void CMapObject::moveTo ( int x, int y, int z ) {
	move ( x - posx, y - posy ,z-posz );
}

void CMapObject::moveTo ( Coords coords ) {
	this->moveTo ( coords.x,coords.y,coords.z );
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

void CMapObject::onTurn ( CGameEvent * ) {

}

void CMapObject::onCreate ( CGameEvent * ) {

}

void CMapObject::onDestroy ( CGameEvent * ) {

}

void CMapObject::onMapChanged() {
	this->QObject::setParent ( getMap() );
	if ( this->scene() != getMap()->getScene() ) {
		getMap()->getScene()->addItem ( this );
	}
}



Coords CMapObject::getCoords() {
	return Coords ( posx,posy,posz );
}

void CMapObject::setCoords ( Coords coords ) {
	this->moveTo ( coords.x,coords.y,coords.z );
}
