#include "CTile.h"

#include "CGameScene.h"
#include "CConfigurationProvider.h"

std::map<QString, std::function<void() > > CTile::steps {
	{ "RoadTile", RoadTile }
};

CTile::CTile ( QString name, int x, int y, int z ) {
	setXYZ ( x, y, z );
	//loadFromJson ( name );
}

CTile::CTile() {}

CTile::CTile ( const CTile &tile )
	: CTile ( tile.typeName, tile.getPosX(), tile.getPosY(), tile.getPosZ() ) {}

CTile::~CTile() {}

void CTile::moveTo ( int x, int y, int z, bool silent ) {
	if ( init && map ) {
		if ( map->find ( Coords ( posx, posy, posz ) ) != map->end() ) {
			map->erase ( map->find ( Coords ( posx, posy, posz ) ) );
		}
		setXYZ ( x, y, z );
		map->insert (
		    std::pair<Coords, CTile*> ( Coords ( posx, posy, posz ), this ) );
	}
	//CMapObject::moveTo ( x, y, z, silent );
	init = true;
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
	setPos ( posx *50, posy *50 );
	CMapObject::setMap (  scene ->getMap() );
}

void CTile::removeFromScene ( CGameScene *scene ) { scene->removeItem ( this ); }

void CTile::loadFromJson ( QString name ) {
	this->typeName = name;
	QJsonObject config =
	    CConfigurationProvider::getConfig ( "config/tiles.json" ).toObject() [typeName].toObject();
	step = config["canStep"].toBool();
	setAnimation ( config["path"].toString() );
}

void CTile::setDraggable() { draggable = true; }

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
