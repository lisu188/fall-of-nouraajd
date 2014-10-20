#pragma once
#include <list>
#include <QTimer>
#include <QObject>
#include <qgraphicsitemanimation.h>
#include <QTimeLine>
#include "CAnimation.h"
#include "CAnimatedObject.h"
#include "CEventHandler.h"
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
#include <boost/python.hpp>
#include "CScriptLoader.h"

class CGameScene;
class CTile;
class CPlayer;
class CLootProvider;
class CInteraction;
class CObjectHandler;
class CScriptEngine;
class CGuiHandler;

class CMap : public QObject,
	private std::unordered_map<Coords, CTile*> {
	Q_OBJECT
public:
	CMap ( CGameScene *scene, QString mapPath );
	virtual ~CMap();
	bool addTile ( CTile *tile, int x, int y, int z );
	void removeTile ( int x, int y, int z );
	void move ();
	CTile *getTile ( int x, int y, int z );
	bool contains ( int x, int y, int z );
	void addObject ( CMapObject *mapObject );
	void removeObject ( CMapObject *mapObject );
	void ensureSize();
	CGameScene *getScene() const;
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
	void moveTile ( CTile* tile,int x, int y, int z );
	void handleTileLayer ( const QJsonObject& tileset,const QJsonObject& layer );
	void handleObjectLayer ( const QJsonObject &layer );
	const CLootProvider *getLootProvider() const;
	const CObjectHandler *getObjectHandler() const;
	const CEventHandler *getEventHandler() const;
	CGuiHandler *getGuiHandler() const;
	Q_INVOKABLE bool canStep ( int x,int y,int z );
	Q_SIGNAL void nextMove();
	bool canStep ( Coords &coords );
	QString getMapPath() const;
	QString getMapName();
	CMapObject *getObjectByName ( QString name );
	template<typename T>
	std::set<CMapObject *> getIf ( T func ) {
		std::set<CMapObject *> objects;
		for ( auto it : mapObjects ) {
			if ( func ( it.second  ) ) {
				objects.insert ( it.second );
			}
		}
		return objects;
	}
	template<typename T,typename U=bool ( CMapObject* ) >
	void forAll ( T func ,U predicate=[] ( CMapObject* ) {return true;} ) {
		for ( CMapObject* object : getMapObjectsClone() ) {
			if ( predicate ( object ) ) {
				func ( object  );
			}
		}
	}
	template<typename T>
	void removeAll ( T func ) {
		QList<CMapObject*> objects;
		for ( auto it : mapObjects ) {
			if ( func ( it.second ) ) {
				objects.append ( it.second  );
			}
		}
		for ( auto it : objects ) {
			removeObject ( it );
		}
	}
	void applyEffects();
private:
	std::set<CMapObject *> getMapObjectsClone();
	void resolveFights();
	void loadMap ( QString mapPath );
	std::unordered_map<QString,CMapObject *> mapObjects;
	CGameScene *scene=0;
	int currentLevel = 0;
	std::map<int, QString> defaultTiles;
	std::map<int, std::pair<int, int> > boundaries;
	int entryx, entryz, entryy;
	CLootProvider *lootProvider=0;
	CObjectHandler *handler=0;
	CEventHandler *eventHandler=0;
	CGuiHandler *guiHandler=0;
	CMapScriptLoader *loader=0;
	QString mapPath;
};

