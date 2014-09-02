#include "tile.h"

#include <src/gamescene.h>
#include "CConfigurationProvider.h"

std::unordered_map<std::string, std::function<void() > > Tile::steps {
	{ "RoadTile", RoadTile }
};

Tile::Tile ( std::string name, int x, int y, int z ) : CMapObject ( x, y, z, 1 ) {
	setXYZ ( x, y, z );
	loadFromJson ( name );
}

Tile::Tile ( QString name, int x, int y, int z ) :Tile ( name.toStdString(),x,y,z ) {

}

Tile::Tile() {}

Tile::Tile ( const Tile &tile )
	: Tile ( tile.typeName, tile.getPosX(), tile.getPosY(), tile.getPosZ() ) {}

Tile::~Tile() {}

void Tile::moveTo ( int x, int y, int z, bool silent ) {
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

Coords Tile::getCoords() { return Coords ( posx, posy, posz ); }

void Tile::onStep() {
	if ( steps.find ( typeName ) != steps.end() ) {
		steps[typeName]();
	}
}

bool Tile::canStep() const { return step; }

Tile *Tile::getTile ( std::string type, int x, int y, int z ) {
	return new Tile ( type, x, y, z );
}

void Tile::addToScene ( CGameScene *scene ) {
	setPos ( posx * CMap::getTileSize(), posy * CMap::getTileSize() );
	CMapObject::setMap (  scene ->getMap() );
}

void Tile::removeFromScene ( CGameScene *scene ) { scene->removeItem ( this ); }

void Tile::loadFromJson ( std::string name ) {
	this->typeName = name;
	Json::Value config =
	    ( *CConfigurationProvider::getConfig ( "config/tiles.json" ) ) [typeName];
	step = config.get ( "canStep", true ).asBool();
	setAnimation ( config.get ( "path", "" ).asCString() );
}

void Tile::setDraggable() { draggable = true; }

void Tile::setXYZ ( int x, int y, int z ) {
	posx = x;
	posy = y;
	posz = z;
}

void Tile::mousePressEvent ( QGraphicsSceneMouseEvent *event ) {
	if ( draggable ) {
		CAnimatedObject::mousePressEvent ( event );
	}
	event->setAccepted ( draggable );
}

bool Tile::canSave() { return false; }

void Tile::setMap ( CMap *map ) {
	this->map = map;
	addToScene ( map->getScene() );
}

void RoadTile() { /*GameScene::getPlayer()->heal(1); */}
