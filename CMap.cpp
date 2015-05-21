#include "CMap.h"
#include "CPathFinder.h"
#include "CGame.h"
#include "object/CObject.h"
#include "provider/CProvider.h"
#include "gui/CGui.h"
#include "handler/CHandler.h"
#include "CUtil.h"
#include "CMapLoader.h"
#include "CThreadUtil.h"

CMap::CMap ( CGame *game, QString mapPath ) :game ( game ),mapPath ( mapPath ) {
    qDebug() <<"Initializing map"<<"\n";
    CMapLoader::loadMap ( this, mapPath );
    qDebug() <<"Loaded map"<<"\n";
}

CMap::~CMap() {

}

void CMap::ensureTile ( int i, int j ) {
    Coords coords ( i, j, currentLevel );
    if ( find ( coords ) == end() ) {
        this->getTile ( i, j, currentLevel );
    }
}

std::map<int, std::pair<int, int> > CMap::getBounds() {
    return boundaries;
}

int CMap::getCurrentXBound() {
    return boundaries[currentLevel].first;
}

int CMap::getCurrentYBound() {
    return boundaries[currentLevel].second;
}

void CMap::removeObjectByName ( QString name ) {
    this->removeObject ( this->getObjectByName ( name ) );
}

QString CMap::addObjectByName ( QString name, Coords coords ) {
    if (   this->canStep ( coords ) ) {
        CMapObject *object = createObject<CMapObject*> ( name );
        if ( object ) {
            addObject ( object );
            object->moveTo ( coords.x, coords.y, coords.z );
            qDebug() << "Added object" << object->getObjectType() << "with name"
                     << object->objectName() << "on" << coords.x << coords.y << coords.z << "\n";
            return name;
        }
    }
    return nullptr;
}

void CMap::replaceTile ( QString name, Coords coords ) {
    removeTile ( coords.x, coords.y, coords.z );
    addTile ( createObject<CTile*> ( name ), coords.x, coords.y, coords.z );
}

Coords CMap::getLocationByName ( QString name ) {
    return this->getObjectByName ( name )->getCoords();
}

CPlayer *CMap::getPlayer() {
    return player;
}

void CMap::setPlayer ( CPlayer *player ) {
    assert ( !this->player );
    addObject ( player );
    player->moveTo ( entryx, entryy, entryz );
    this->player=player;
}

CLootHandler *CMap::getLootHandler()  {
    return lootHandler.get ( this );
}

CObjectHandler *CMap::getObjectHandler()  {
    return objectHandler.get ( getGame()->getObjectHandler() );
}

CEventHandler *CMap::getEventHandler()  {
    return eventHandler.get (  );
}

CMouseHandler *CMap::getMouseHandler()  {
    return mouseHandler.get (  );
}

void CMap::moveTile ( CTile *tile, int x, int y, int z ) {
    Coords coords=tile->getCoords();
    auto it=find ( coords ) ;
    if ( it !=end() ) {
        erase ( it );
    }
    insert ( std::make_pair ( Coords ( x,y,z ), tile ) );
}

void CMap::ensureSize() {
    CPlayer * player=nullptr;
    if ( !this->getGame() ||! ( player=this->getGame()->getMap() ->getPlayer() ) ) {
        return;
    }
    for ( int i=-25; i<25; i++ ) {
        for ( int j=-15; j<15; j++ ) {
            ensureTile ( player->getPosX()+i,player->getPosY()+j );
        }
    }

    currentLevel = player->getPosZ();

    for ( auto it :mapObjects ) {
        ( it.second )->setVisible ( ( it.second )->getPosZ() == currentLevel );
    }

    if ( game->getView() ) {
        game->getView()->centerOn ( player );
    }
}

bool CMap::addTile ( CTile * tile, int x, int y, int z ) {
    if ( this->contains ( x, y, z ) ) {
        return false;
    }
    tile->addToScene ( this->game );
    tile->moveTo ( x,y,z );
    tile->setVisible ( true );
    return true;
}

void CMap::removeTile ( int x, int y, int z ) {
    this->erase ( this->find ( Coords ( x, y, z ) ) );
}

int CMap::getCurrentMap() {
    return currentLevel;
}

CGame *CMap::getGame() const {
    return game;
}

void CMap::mapUp() {
    currentLevel--;
}

void CMap::mapDown() {
    currentLevel++;
}

CTile* CMap::getTile ( int x, int y, int z ) {
    Coords coords ( x, y, z );
    CTile* tile;
    auto it=this->find ( coords );
    if ( it==this->end() ) {
        auto bound = boundaries[z];
        if ( x < 0 || y < 0 || x > bound.first || y > bound.second ) {
            tile=createObject<CTile*> ( "MountainTile" );
        } else {
            tile=createObject<CTile*> ( defaultTiles[z] );
        }
        this->addTile ( tile , x, y, z );
    } else {
        tile= ( *it ).second;
    }
    return tile;
}

CTile *CMap::getTile ( Coords coords ) {
    return this->getTile ( coords.x,coords.y,coords.z );
}

bool CMap::canStep ( int x, int y, int z ) {
    Coords coords ( x, y, z );
    auto it=this->find ( coords );
    if ( it!=this->end() ) {
        return ( *it ).second->canStep();
    }
    std::pair<int,int> bound = boundaries[z];
    return ! ( x < 0 || y < 0 || x > bound.first || y > bound.second );
}

bool CMap::canStep ( const Coords &coords ) {
    return canStep ( coords.x,coords.y,coords.z );
}

QString CMap::getMapPath() const {
    return mapPath;
}

QString CMap::getMapName() {
    return mapPath.replace ( "\\","/" ).split ( "/" ).last();
}

bool CMap::contains ( int x, int y, int z ) {
    Coords coords ( x, y, z );
    iterator it = find ( coords );
    return it != end();
}

void CMap::addObject ( CMapObject *mapObject ) {
    if ( mapObjects.find ( mapObject->objectName() ) !=mapObjects.end() ) {
        qFatal ( QString ( "Map object already exists: "+mapObject->objectName() ).toStdString().c_str() );
    }
    mapObject->setMap ( this );
    CCreature *creature =dynamic_cast<CCreature *> ( mapObject ) ;
    if ( creature ) {
        if ( creature->getLevel() == 0 ) {
            creature->levelUp();
            creature->heal ( 0 );
            creature->addMana ( 0 );
        }
        creature->addExp ( 0 );
    }
    mapObjects.insert ( std::make_pair ( mapObject->objectName(), mapObject ) );
    getEventHandler()->gameEvent ( mapObject ,new CGameEvent ( CGameEvent::Type::onCreate ) );
}

void CMap::removeObject ( CMapObject *mapObject ) {
    if ( getGame() ) {
        getGame()->removeObject ( mapObject );
    }
    mapObjects.erase ( mapObjects.find ( mapObject->objectName() ) );
    getEventHandler()->gameEvent ( mapObject, new CGameEvent ( CGameEvent::Type::onDestroy ) );
}

int CMap::getEntryX() {
    return entryx;
}

int CMap::getEntryY() {
    return entryy;
}

int CMap::getEntryZ() {
    return entryz;
}

CMapObject *CMap::getObjectByName ( QString name ) {
    auto it=mapObjects.find ( name );
    if ( it!=mapObjects.end() ) {
        return ( *it ).second;
    }
    return nullptr;
}

bool CMap::isMoving() {
    return moving;
}



void CMap::applyEffects() {
    for ( CMapObject *object:getIf ( [] ( CMapObject* object ) {
    return dynamic_cast<CCreature*> ( object ) !=nullptr;
    } ) ) {
        dynamic_cast<CCreature*> ( object )->applyEffects();
    }
}

void CMap::move () {
    this->moving=true;

    applyEffects();

    forAll ( [this] ( CMapObject*  mapObject ) {
        getEventHandler()->gameEvent ( mapObject , new CGameEvent ( CGameEvent::Type::onTurn ) );
    } );

    auto target=[] ( CMapObject *object ) {
        return std::make_pair ( object,dynamic_cast<Moveable*> ( object )->getNextMove() );
    };

    auto callback=[] ( std::pair<CMapObject*,Coords> arg ) {
        arg.first->move ( arg.second );
    };

    auto pred=[] ( CMapObject *object ) {
        return dynamic_cast<Moveable*> ( object );
    };

    auto end_callback=[this]() {
        resolveFights();

        ensureSize();

        this->moving=false;
    };

    CThreadUtil::invoke_all ( getIf ( pred ),target,callback,end_callback );
}

std::set<CMapObject *> CMap::getMapObjectsClone() {
    std::set<CMapObject*> objects;
    for ( std::pair<QString,CMapObject*> it:mapObjects ) {
        objects.insert ( it.second );
    }
    return objects;
}

void CMap::resolveFights() {
    forAll ( [this] ( CMapObject *mapObject ) {
        std::set<CMapObject *> objects=getIf ( [&mapObject] ( CMapObject *visitor ) {
            return dynamic_cast<CCreature*> ( mapObject ) &&dynamic_cast<CCreature*> ( visitor ) &&mapObject != visitor && mapObject->getCoords() == visitor->getCoords() ;
        } );
        for ( CMapObject *visitor:objects  ) {
            if ( getObjectByName ( mapObject->objectName() ) && getObjectByName ( visitor->objectName() ) ) {
                dynamic_cast<CCreature*> ( mapObject )->fight ( dynamic_cast<CCreature*> ( visitor ) );
            }
        }
    } );
}


