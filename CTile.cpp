#include "CTile.h"
#include "CGameScene.h"
#include "CMap.h"

CTile::CTile() {
	this->setZValue ( 0 );
}

CTile::CTile ( const CTile & ) {

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

void CTile::addToScene ( CGameScene *scene ) {
	scene->addItem ( this );
	setXYZ (  posx , posy,posz );
}

void CTile::removeFromScene ( CGameScene *scene ) {
	scene->removeItem ( this );
}

void CTile::setXYZ ( int x, int y, int z ) {
	posx = x;
	posy = y;
	posz = z;
	setPos ( x*50,y*50 );
}

void CTile::setObjectName ( const QString &name ) {
	this->QObject::setObjectName ( name );
}

void CTile::setObjectType ( const QString &type ) {
	this->objectType=type;
}

QString CTile::getObjectName() const {
	return this->QObject::objectName();
}

QString CTile::getObjectType() const {
	return this->objectType;
}
CMap *CTile::getMap() {
	return map;
}

void CTile::setMap ( CMap *value ) {
	map = value;
}

