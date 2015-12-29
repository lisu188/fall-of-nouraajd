#include "core/CMap.h"
#include "core/CPathFinder.h"
#include "core/CGame.h"
#include "loader/CLoader.h"
#include "controller/CControllers.h"
#include "vstd.h"

CMap::CMap ( std::shared_ptr<CGame> game ) : game ( game ) {

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
    if ( this->canStep ( coords ) ) {
        std::shared_ptr<CMapObject> object = createObject<CMapObject> ( name );
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
    addTile ( createObject<CTile> ( name ), coords.x, coords.y, coords.z );
}

Coords CMap::getLocationByName ( QString name ) {
    return this->getObjectByName ( name )->getCoords();
}

std::shared_ptr<CPlayer> CMap::getPlayer() {
    return player;
}

void CMap::setPlayer ( std::shared_ptr<CPlayer> player ) {
    addObject ( player );
    player->moveTo ( entryx, entryy, entryz );
    this->player = player;
}

std::shared_ptr<CLootHandler> CMap::getLootHandler() {
    return lootHandler.get ( this->ptr() );
}

std::shared_ptr<CObjectHandler> CMap::getObjectHandler() {
    return objectHandler.get ( getGame()->getObjectHandler() );
}

std::shared_ptr<CEventHandler> CMap::getEventHandler() {
    return eventHandler.get();
}

std::shared_ptr<CMouseHandler> CMap::getMouseHandler() {
    return mouseHandler.get();
}

void CMap::moveTile ( std::shared_ptr<CTile> tile, int x, int y, int z ) {
    Coords coords = tile->getCoords();
    auto it = find ( coords );
    if ( it != end() ) {
        erase ( it );
    }
    insert ( std::make_pair ( Coords ( x, y, z ), tile ) );
}

void CMap::ensureSize() {
    auto player = getPlayer();
    if ( !player ) {
        return;
    }
    for ( int i = -25; i < 25; i++ ) {
        for ( int j = -15; j < 15; j++ ) {
            ensureTile ( player->getPosX() + i, player->getPosY() + j );
        }
    }

    currentLevel = player->getPosZ();

    for ( auto it :mapObjects ) {
        ( it.second )->setVisible ( ( it.second )->getPosZ() == currentLevel );
    }

    if ( getGame()->getView() ) {
        getGame()->getView()->centerOn ( player );
    }
}

bool CMap::addTile ( std::shared_ptr<CTile> tile, int x, int y, int z ) {
    if ( this->contains ( x, y, z ) ) {
        return false;
    }
    tile->moveTo ( x, y, z );
    tile->setVisible ( true );
    return true;
}

void CMap::removeTile ( int x, int y, int z ) {
    this->erase ( this->find ( Coords ( x, y, z ) ) );
}

int CMap::getCurrentMap() {
    return currentLevel;
}

std::shared_ptr<CGame> CMap::getGame() const {
    return game.lock();
}

void CMap::mapUp() {
    currentLevel--;
}

void CMap::mapDown() {
    currentLevel++;
}

std::shared_ptr<CTile> CMap::getTile ( int x, int y, int z ) {
    Coords coords ( x, y, z );
    std::shared_ptr<CTile> tile;
    auto it = this->find ( coords );
    if ( it == this->end() ) {
        auto bound = boundaries[z];
        if ( x < 0 || y < 0 || x > bound.first || y > bound.second ) {
            tile = createObject<CTile> ( "MountainTile" );
        } else {
            tile = createObject<CTile> ( defaultTiles[z] );
        }
        this->addTile ( tile, x, y, z );
    } else {
        tile = ( *it ).second;
    }
    return tile;
}

std::shared_ptr<CTile> CMap::getTile ( Coords coords ) {
    return this->getTile ( coords.x, coords.y, coords.z );
}

bool CMap::canStep ( int x, int y, int z ) {
    Coords coords ( x, y, z );
    auto it = this->find ( coords );
    if ( it != this->end() ) {
        return ( *it ).second->canStep();
    }
    std::pair<int, int> bound = boundaries[z];
    return ! ( x < 0 || y < 0 || x > bound.first || y > bound.second );
}

bool CMap::canStep ( const Coords &coords ) {
    return canStep ( coords.x, coords.y, coords.z );
}

bool CMap::contains ( int x, int y, int z ) {
    Coords coords ( x, y, z );
    iterator it = find ( coords );
    return it != end();
}

void CMap::addObject ( std::shared_ptr<CMapObject> mapObject ) {
    vstd::fail_if ( vstd::ctn ( mapObjects, mapObject->objectName() ),
                    "Map object already exists: " + mapObject->objectName() );
    mapObject->setMap ( this->ptr() );
    std::shared_ptr<CCreature> creature = vstd::cast<CCreature> ( mapObject );
    if ( creature.get() ) {
        if ( creature->getLevel() == 0 ) {
            creature->levelUp();
            creature->heal ( 0 );
            creature->addMana ( 0 );
        }
        creature->addExp ( 0 );
    }
    mapObjects.insert ( std::make_pair ( mapObject->objectName(), mapObject ) );
    getEventHandler()->gameEvent ( mapObject, std::make_shared<CGameEvent> ( CGameEvent::Type::onCreate ) );
}

void CMap::removeObject ( std::shared_ptr<CMapObject> mapObject ) {
    mapObject->setVisible ( false );
    mapObjects.erase ( mapObjects.find ( mapObject->objectName() ) );
    getEventHandler()->gameEvent ( mapObject, std::make_shared<CGameEvent> ( CGameEvent::Type::onDestroy ) );
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

std::shared_ptr<CMapObject> CMap::getObjectByName ( QString name ) {
    auto it = mapObjects.find ( name );
    if ( it != mapObjects.end() ) {
        return ( *it ).second;
    }
    return std::shared_ptr<CMapObject>();
}

bool CMap::isMoving() {
    return moving;
}

void CMap::applyEffects() {
    auto pred = [] ( std::shared_ptr<CMapObject> object ) {
        return vstd::castable<CCreature> ( object );
    };
    for ( std::shared_ptr<CMapObject> object:mapObjects |
            boost::adaptors::map_values |
            boost::adaptors::filtered ( pred ) ) {
        vstd::cast<CCreature> ( object )->applyEffects();
    }
}

void CMap::forObjects ( std::function<void ( std::shared_ptr<CMapObject> ) > func,
                        std::function<bool ( std::shared_ptr<CMapObject> ) > predicate ) {
    auto clone = mapObjects;
    for ( std::shared_ptr<CMapObject> object : clone |
            boost::adaptors::map_values |
            boost::adaptors::filtered ( predicate ) ) {
        func ( object );
    }
}

void CMap::forTiles ( std::function<void ( std::shared_ptr<CTile> ) > func,
                      std::function<bool ( std::shared_ptr<CTile> ) > predicate ) {
    for ( std::shared_ptr<CTile> tile:*dynamic_cast<std::unordered_map<Coords, std::shared_ptr<CTile>> *> ( this ) |
            boost::adaptors::map_values |
            boost::adaptors::filtered ( predicate ) ) {
        func ( tile );
    }
}

void CMap::removeObjects ( std::function<bool ( std::shared_ptr<CMapObject> ) > func ) {
    auto clone = mapObjects;
    for ( std::shared_ptr<CMapObject> object : clone |
            boost::adaptors::map_values |
            boost::adaptors::filtered ( func ) ) {
        removeObject ( object );
    }
}

void CMap::move() {
    static std::shared_ptr<vstd::future<void, void>> move = vstd::later ( []() { } );
    auto map = this->ptr();

    move = move->thenLater ( [map]() {
        vstd::wait_until ( [map]() {
            return !map->moving;
        } );

        map->moving = true;

        map->applyEffects();

        map->forObjects ( [map] ( std::shared_ptr<CMapObject> mapObject ) {
            map->getEventHandler()->gameEvent ( mapObject, std::make_shared<CGameEvent> ( CGameEvent::Type::onTurn ) );
        } );

        auto pred = [] ( std::shared_ptr<CMapObject> object ) {
            return vstd::castable<Moveable> ( object ) && !vstd::castable<CPlayer> ( object );
        };

        auto controller = [map] ( std::shared_ptr<CMapObject> object ) {
            return std::make_shared<CTargetController> ( map->getPlayer() )->control ( vstd::cast<CCreature> ( object ) );
        };

        auto end_callback = [map] ( std::set<void *> ) {
            map->resolveFights();

            map->ensureSize();

            if ( QApplication::instance()->property ( "auto_save" ).toBool() ) {
                CMapLoader::saveMap ( map, QString::number ( QDateTime::currentMSecsSinceEpoch() ) + ".sav" );
            }

            map->moving = false;
        };

        vstd::join ( map->mapObjects |
                     boost::adaptors::map_values |
                     boost::adaptors::filtered ( pred ) |
                     boost::adaptors::transformed ( controller ) )
        ->thenLater ( end_callback );
    } );
}

void CMap::resolveFights() {
    forObjects ( [this] ( std::shared_ptr<CMapObject> mapObject ) {
        auto action = [this, mapObject] ( std::shared_ptr<CMapObject> visitor ) {
            if ( getObjectByName ( mapObject->objectName() ) && getObjectByName ( visitor->objectName() ) ) {
                vstd::cast<CCreature> ( mapObject )->fight ( vstd::cast<CCreature> ( visitor ) );
            }
        };
        auto pred = [mapObject] ( std::shared_ptr<CMapObject> visitor ) {
            return vstd::cast<CCreature> ( mapObject ) && vstd::cast<CCreature> ( visitor ) && mapObject != visitor &&
                   mapObject->getCoords() == visitor->getCoords();
        };
        forObjects ( action, pred );
    } );
}

std::shared_ptr<CMap> CMap::ptr() {
    return shared_from_this();
}


