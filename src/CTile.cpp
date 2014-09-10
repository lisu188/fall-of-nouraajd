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

CTile::CTile ( const CTile &tile )
{}

CTile::~CTile() {

}

void CTile::moveTo ( int x, int y, int z, bool silent ) {
	if (  map ) {
		map->moveTile ( this,x,y, z );
		setXYZ ( x, y, z );
	}
}

Coords CTile::getCoords() { return Coords ( posx, posy, posz ); }

void CTile::onStep() {
	if ( steps.find ( typeName ) != steps.end() ) {
		steps[typeName]();
	}
}

bool CTile::canStep() const { return step; }

void CTile::setCanStep ( bool canStep ) {
	this->step=canStep;
}

void CTile::addToScene ( CGameScene *scene ) {
	scene->addItem ( this );
	setPos ( posx *50, posy *50 );
	CMapObject::setMap (  scene ->getMap() );
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

bool CTile::canSave() { return false; }

void CTile::setMap ( CMap *map ) {
	this->map = map;
	addToScene ( map->getScene() );
}

void RoadTile() { /*GameScene::getPlayer()->heal(1); */}
