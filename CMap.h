#pragma once
#include "CGlobal.h"

#include "CUtil.h"
#include "object/CObject.h"
#include "handler/CHandler.h"
#include "provider/CProvider.h"

class CGame;
class CTile;
class CPlayer;
class CLootHandler;
class CInteraction;
class CObjectHandler;
class CScriptHandler;
class CGuiHandler;

class CMap : public QObject,
    private std::unordered_map<Coords, CTile*> {
    friend class CMapLoader;
    Q_OBJECT
public:
    CMap ( CGame *game, QString mapPath );
    virtual ~CMap();
    bool addTile ( CTile *tile, int x, int y, int z );
    void removeTile ( int x, int y, int z );
    void move ();
    CTile *getTile ( int x, int y, int z );
    CTile *getTile ( Coords coords );
    bool contains ( int x, int y, int z );
    void addObject ( CMapObject *mapObject );
    void removeObject ( CMapObject *mapObject );
    void ensureSize();
    CGame *getGame() const;
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
    QString addObjectByName ( QString name,Coords coords );
    void replaceTile ( QString name,Coords coords );
    Coords getLocationByName ( QString name );
    CPlayer *getPlayer();
    void setPlayer ( CPlayer *player );
    void moveTile ( CTile* tile,int x, int y, int z );
    CLootHandler *getLootHandler();
    CObjectHandler *getObjectHandler() ;
    CEventHandler *getEventHandler() ;
    CMouseHandler *getMouseHandler() ;
    bool canStep ( int x,int y,int z );
    bool canStep ( const Coords &coords );
    QString getMapPath() const;
    QString getMapName();
    CMapObject *getObjectByName ( QString name );
    bool isMoving();
    void applyEffects();
    std::set<CMapObject *> getIf (  std::function<bool ( CMapObject* ) > func );
    void forAll ( std::function<void ( CMapObject* ) > func , std::function<bool ( CMapObject* ) >  predicate=[] ( CMapObject* ) {return true;} );
    void removeAll ( std::function<bool ( CMapObject* ) > func );
    template<typename T>
    T createObject ( QString name ) {
        return getObjectHandler()->createObject<T> ( this,name );
    }
private:
    std::set<CMapObject *> getMapObjectsClone();
    void resolveFights();
    std::unordered_map<QString,CMapObject *> mapObjects;
    CGame *game=0;
    CPlayer *player=0;
    int currentLevel = 0;
    std::map<int, QString> defaultTiles;
    std::map<int, std::pair<int, int> > boundaries;
    int entryx, entryz, entryy;
    Lazy<CLootHandler,CMap*> lootHandler;
    Lazy<CObjectHandler,CObjectHandler*> objectHandler;
    Lazy<CEventHandler> eventHandler;
    Lazy<CMouseHandler> mouseHandler;
    QString mapPath;
    bool moving=false;
};

