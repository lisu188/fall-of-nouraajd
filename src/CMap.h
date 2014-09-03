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
#include <lib/json/json.h>
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
	public std::unordered_map<Coords, std::string, CoordsHasher> {
	Q_OBJECT
public:
	CMap ( CGameScene *scene, std::string file );
	~CMap();
	bool addTile ( std::string name, int x, int y, int z );
	bool removeTile ( int x, int y, int z );
	static int getTileSize();
	void move ( int x, int y );
	std::string getTile ( int x, int y, int z );
	bool contains ( int x, int y, int z );
	void addObject ( CMapObject *mapObject );
	void addRiver ( int length, int startx, int starty, int startz );
	void addRoad ( int length, int startx, int starty, int startz );
	void addDungeon ( Coords enter, Coords exit, int width, int height );
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
	CMapObject *getObjectByName ( std::string name );
	Q_SLOT void moveCompleted();
	Q_INVOKABLE inline void ensureTile ( int i, int j );
	std::unordered_map<Coords, CTile *, CoordsHasher> tiles;
	std::map<int, std::pair<int, int> > getBounds();
	int getCurrentXBound();
	int getCurrentYBound();
	CScriptEngine *getEngine();
	bool removeObjectByName ( std::string name );
	std::string addObjectByName ( std::string name,Coords coords );
	void replaceTile ( std::string name,Coords coords );
	Coords getLocationByName ( std::string name );
	CPlayer *getPlayer();
	CLootProvider *getLootProvider();
	void loadingComplete();
	template<typename T>
	T createMapObject ( std::string name ) {
		return createMapObject<T> ( QString::fromStdString ( name ) );
	}
	template<typename T>
	std::string getClassName ( QString name ) {
		Json::Value config = ( *CConfigurationProvider::getConfig (
		                           "config/object.json" ) ) [name.toStdString()];
		if ( config.isNull() ) {
			return "";
		}
		return config.get ( "class", "" ).asString();
	}
	template<typename T>
	T createMapObject ( QString name ) {
		CMapObject *object = NULL;
		std::string className = getClassName<T> ( name );
		object=this->engine->createObject<CMapObject*> ( className );
		if ( object==NULL ) {
			int typeId = QMetaType::type ( className.c_str() );
			if ( typeId == 0 ) {
				return NULL;
			}
			object = ( CMapObject * ) QMetaType::create ( typeId );
		}
		std::stringstream stream;
		stream << std::hex << ( unsigned long ) object;
		std::string result ( stream.str() );
		object->name = result;
		object->map=this;
		object->loadFromJson ( name.toStdString() );
		return dynamic_cast<T> ( object );
	}
private:
	std::set<CMapObject *> mapObjects;
	void randomDir ( int *tab, int rule );
	CGameScene *scene;
	int currentMap = 0;
	std::map<int, std::string> defaultTiles;
	std::map<int, std::pair<int, int> > boundaries;
	int entryx, entryz, entryy;
	CScriptEngine *engine;
	CLootProvider *lootProvider;
};

