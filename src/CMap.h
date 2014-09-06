#pragma once
#include "CScriptEngine.h"
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
#include <lib/tmx/TmxMap.h>
#include <QGraphicsScene>
#include <QString>
#include <string>
#include "CConfigurationProvider.h"
#include "CMapObject.h"
#include "Util.h"

class CGameScene;
class CTile;
class CPlayer;
class CLootProvider;
class CInteraction;


class CMap : public QObject,
	public std::unordered_map<Coords, QString, CoordsHasher> {
	Q_OBJECT
public:
	CMap ( CGameScene *scene, QString file );
	~CMap();
	bool addTile ( QString name, int x, int y, int z );
	void removeTile ( int x, int y, int z );
	static int getTileSize();
	void move ( int x, int y );
	QString getTile ( int x, int y, int z );
	bool contains ( int x, int y, int z );
	void addObject ( CMapObject *mapObject );
	void addRiver ( int length, int startx, int starty, int startz );
	void addRoad ( int length, int startx, int starty, int startz );
	void removeObject ( CMapObject *mapObject );
	Q_SLOT void ensureSize();
	void hide();
	CGameScene *getScene() const;
	void showAll();
	void mapUp();
	void mapDown();
	int getCurrentMap();
	std::set<CMapObject *> *getObjects();
	void loadMapFromTmx ( Tmx::Map &map );
	int getEntryX();
	int getEntryY();
	int getEntryZ();
	CMapObject *getObjectByName ( QString name );
	Q_SLOT void moveCompleted();
	Q_INVOKABLE void ensureTile ( int i, int j );
	std::unordered_map<Coords, CTile *, CoordsHasher> tiles;
	std::map<int, std::pair<int, int> > getBounds();
	int getCurrentXBound();
	int getCurrentYBound();
	CScriptEngine *getEngine();
	void removeObjectByName ( QString name );
	QString addObjectByName ( QString name,Coords coords );
	void replaceTile ( QString name,Coords coords );
	Coords getLocationByName ( QString name );
	CPlayer *getPlayer();
	CLootProvider *getLootProvider();
	void loadingComplete();
	template<typename T>
	QString getClassName ( QString name ) {
		QJsonObject config = CConfigurationProvider::getConfig (
		                         "config/object.json" ).toObject() [name].toObject();
		if ( config.isEmpty() ) {
			return "";
		}
		return config[ "class" ].toString();
	}
	template<typename T>
	T createMapObject ( QString name ) {
		CMapObject *object = NULL;
		QString className = getClassName<T> ( name );
		object=this->engine->createObject<CMapObject*> ( className );
		if ( object==NULL ) {
			int typeId = QMetaType::type ( className.toStdString().c_str() );
			if ( typeId == 0 ) {
				return NULL;
			}
			object = ( CMapObject * ) QMetaType::create ( typeId );
		}
		std::stringstream stream;
		stream << std::hex << (   long ) object;
		QString result ( stream.str().c_str() );
		object->name = result;
		object->map=this;
		object->loadFromJson ( name );
		return dynamic_cast<T> ( object );
	}
private:
	std::set<CMapObject *> mapObjects;
	void randomDir ( int *tab, int rule );
	CGameScene *scene;
	int currentMap = 0;
	std::map<int, QString> defaultTiles;
	std::map<int, std::pair<int, int> > boundaries;
	int entryx, entryz, entryy;
	CScriptEngine *engine;
	CLootProvider *lootProvider;
};

