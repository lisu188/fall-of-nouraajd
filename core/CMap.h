#pragma once

#include "core/CGlobal.h"

#include "core/CUtil.h"
#include "handler/CHandler.h"
#include "provider/CProvider.h"
#include "templates/lazy.h"

class CGame;

class CTile;

class CPlayer;

class CLootHandler;

class CInteraction;

class CObjectHandler;

class CScriptHandler;

class CEventHandler;

class CMouseHandler;

class CGuiHandler;

class CMapObject;

class CMap : public QObject,
    private std::unordered_map<Coords, std::shared_ptr<CTile>>, public std::enable_shared_from_this<CMap> {
    friend class CMapLoader;

    Q_OBJECT
public:
    CMap ( std::shared_ptr<CGame> game );

    bool addTile ( std::shared_ptr<CTile> tile, int x, int y, int z );

    void removeTile ( int x, int y, int z );

    void move();

    std::shared_ptr<CTile> getTile ( int x, int y, int z );

    std::shared_ptr<CTile> getTile ( Coords coords );

    bool contains ( int x, int y, int z );

    void addObject ( std::shared_ptr<CMapObject> mapObject );

    void removeObject ( std::shared_ptr<CMapObject> mapObject );

    void ensureSize();

    std::shared_ptr<CGame> getGame() const;

    void mapUp();

    void mapDown();

    int getCurrentMap();

    int getEntryX();

    int getEntryY();

    int getEntryZ();

    void ensureTile ( int i, int j );

    std::map<int, std::pair<int, int> > getBounds();

    int getCurrentXBound();

    int getCurrentYBound();

    void removeObjectByName ( QString name );

    QString addObjectByName ( QString name, Coords coords );

    void replaceTile ( QString name, Coords coords );

    Coords getLocationByName ( QString name );

    std::shared_ptr<CPlayer> getPlayer();

    void setPlayer ( std::shared_ptr<CPlayer> player );

    void moveTile ( std::shared_ptr<CTile> tile, int x, int y, int z );

    std::shared_ptr<CLootHandler> getLootHandler();

    std::shared_ptr<CObjectHandler> getObjectHandler();

    std::shared_ptr<CEventHandler> getEventHandler();

    std::shared_ptr<CMouseHandler> getMouseHandler();

    bool canStep ( int x, int y, int z );

    bool canStep ( const Coords &coords );

    std::shared_ptr<CMapObject> getObjectByName ( QString name );

    bool isMoving();

    void applyEffects();

    void forObjects ( std::function<void ( std::shared_ptr<CMapObject> ) > func,
                      std::function<bool ( std::shared_ptr<CMapObject> ) > predicate = [] (
    std::shared_ptr<CMapObject> ) { return true; } );

    void forTiles ( std::function<void ( std::shared_ptr<CTile> ) > func,
    std::function<bool ( std::shared_ptr<CTile> ) > predicate = [] ( std::shared_ptr<CTile> ) { return true; } );

    void removeObjects ( std::function<bool ( std::shared_ptr<CMapObject> ) > func );

    template<typename T>
    std::shared_ptr<T> createObject ( QString name ) {
        return getObjectHandler()->createObject<T> ( this->ptr(), name );
    }

    std::shared_ptr<CMap> ptr();

private:
    void resolveFights();

    std::unordered_map<QString, std::shared_ptr<CMapObject>> mapObjects;
    std::weak_ptr<CGame> game;
    std::shared_ptr<CPlayer> player;
    int currentLevel = 0;
    std::map<int, QString> defaultTiles;
    std::map<int, std::pair<int, int> > boundaries;
    int entryx, entryz, entryy;
    vstd::lazy<CLootHandler, std::shared_ptr<CMap>> lootHandler;
    vstd::lazy<CObjectHandler, std::shared_ptr<CObjectHandler>> objectHandler;
    vstd::lazy<CEventHandler> eventHandler;
    vstd::lazy<CMouseHandler> mouseHandler;
    bool moving = false;
};

