#include "CTile.h"
#include "CGameScene.h"
#include "CConfigurationProvider.h"
#include <QDebug>

std::map<QString, std::function<void() > > CTile::steps {
	{ "RoadTile", RoadTile }
};

CTile::CTile() {
	this->setZValue ( 0 );
}

CTile::CTile ( const CTile & )
{}

CTile::~CTile() {

}

void CTile::moveTo ( int x, int y, int z ) {
	if (  getMap() ) {
		getMap()->moveTile ( this,x,y, z );
		setXYZ ( x, y, z );
	}
}

Coords CTile::getCoords() { return Coords ( posx, posy, posz ); }

void CTile::onStep() {
	if ( steps.find ( getTypeName() ) != steps.end() ) {
		steps[getTypeName()]();
	}
}

bool CTile::canStep() const {
	return step;
}

void CTile::setCanStep ( bool canStep ) {
	this->step=canStep;
}

void CTile::addToScene ( CGameScene *scene ) {
	scene->addItem ( this );
	setPos ( posx *50, posy *50 );
	setMap (  scene ->getMap() );
}

void CTile::removeFromScene ( CGameScene *scene ) { scene->removeItem ( this ); }

void CTile::setDraggable() { draggable = true; }

void CTile::onEnter() {}

void CTile::onMove() {}

void CTile::setXYZ ( int x, int y, int z ) {
	posx = x;
	posy = y;
	posz = z;
	setPos ( x*50,y*50 );
}

void CTile::mousePressEvent ( QGraphicsSceneMouseEvent *event ) {
	if ( draggable ) {
		CAnimatedObject::mousePressEvent ( event );
	}
	event->setAccepted ( draggable );
}

void RoadTile() { /*GameScene::getPlayer()->heal(1); */}
