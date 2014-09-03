#include "CTile.h"

#include "CGameScene.h"
#include "CConfigurationProvider.h"

std::unordered_map<std::string, std::function<void() > > CTile::steps {
	{ "RoadTile", RoadTile }
};

CTile::CTile ( std::string name, int x, int y, int z ) : CMapObject ( x, y, z, 1 ) {
	setXYZ ( x, y, z );
	loadFromJson ( name );
}

CTile::CTile ( QString name, int x, int y, int z ) :CTile ( name.toStdString(),x,y,z ) {

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
		    std::pair<Coords, std::string> ( Coords ( posx, posy, posz ), typeName ) );
	}
	CMapObject::moveTo ( x, y, z, silent );
	init = true;
}

Coords CTile::getCoords() { return Coords ( posx, posy, posz ); }

void CTile::onStep() {
	if ( steps.find ( typeName ) != steps.end() ) {
		steps[typeName]();
	}
}

bool CTile::canStep() const { return step; }

CTile *CTile::getTile ( std::string type, int x, int y, int z ) {
	return new CTile ( type, x, y, z );
}

void CTile::addToScene ( CGameScene *scene ) {
	setPos ( posx * CMap::getTileSize(), posy * CMap::getTileSize() );
	CMapObject::setMap (  scene ->getMap() );
}

void CTile::removeFromScene ( CGameScene *scene ) { scene->removeItem ( this ); }

void CTile::loadFromJson ( std::string name ) {
	this->typeName = name;
	Json::Value config =
	    ( *CConfigurationProvider::getConfig ( "config/tiles.json" ) ) [typeName];
	step = config.get ( "canStep", true ).asBool();
	setAnimation ( config.get ( "path", "" ).asCString() );
}

void CTile::setDraggable() { draggable = true; }

void CTile::setXYZ ( int x, int y, int z ) {
	posx = x;
	posy = y;
	posz = z;
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
