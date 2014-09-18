#pragma once
#include <list>
#include <QTimer>
#include <QObject>
#include <qgraphicsitemanimation.h>
#include <QTimeLine>
#include "CAnimation.h"
#include "CAnimatedObject.h"
#include <unordered_map>
#include <set>
#include <QJsonObject>
#include <QGraphicsScene>
#include <QString>
#include <string>
#include "CConfigurationProvider.h"
#include "CMapObject.h"
#include "Util.h"
#include <mutex>

class CGameScene;
class CTile;
class CPlayer;
class CLootProvider;
class CInteraction;
class CObjectHandler;
class CScriptEngine;

class CMap : public QObject,
    private std::unordered_map<Coords, CTile*, CoordsHasher> {
    friend class std::unique_lock<CMap>;
    Q_OBJECT
public:
    CMap ( CGameScene *scene, QString file );
    virtual ~CMap();
    bool addTile ( CTile *tile, int x, int y, int z );
    void removeTile ( int x, int y, int z );
    void move ( int x, int y );
    CTile *getTile ( int x, int y, int z );
    Q_INVOKABLE bool canStep ( int x,int y,int z );
    bool contains ( int x, int y, int z );
    void addObject ( CMapObject *mapObject );
    void removeObject ( CMapObject *mapObject );
    Q_SLOT void ensureSize();
    CGameScene *getScene() const;
    void mapUp();
    void mapDown();
    int getCurrentMap();
    std::set<CMapObject *> *getObjects();
    int getEntryX();
    int getEntryY();
    int getEntryZ();
    CMapObject *getObjectByName ( QString name );
    Q_SLOT void moveCompleted();
    Q_INVOKABLE void ensureTile ( int i, int j );
    std::map<int, std::pair<int, int> > getBounds();
    int getCurrentXBound();
    int getCurrentYBound();
    void removeObjectByName ( QString name );
    QString addObjectByName ( QString name,Coords coords );
    void replaceTile ( QString name,Coords coords );
    Coords getLocationByName ( QString name );
    CPlayer *getPlayer();
    CLootProvider *getLootProvider();
    CObjectHandler *getObjectHandler();
    void loadingComplete();
    void moveTile ( CTile* tile,int x, int y, int z );
    void loadMap ( const QJsonObject &map );
    void handleTileLayer ( const QJsonObject& tileset,const QJsonObject& layer );
    void handleObjectLayer ( const QJsonObject &layer );
private:
    std::set<CMapObject *> mapObjects;
    void randomDir ( int *tab, int rule );
    CGameScene *scene;
    int currentMap = 0;
    std::map<int, QString> defaultTiles;
    std::map<int, std::pair<int, int> > boundaries;
    int entryx, entryz, entryy;
    CLootProvider *lootProvider;
    CObjectHandler *handler;
};

