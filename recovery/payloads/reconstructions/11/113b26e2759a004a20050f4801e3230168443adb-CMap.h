#pragma once
#include "scriptmanager.h"
#include <list>
#include <type_traits>
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
#include "util.h"

class Comparer {
  public:
    bool operator()(CMapObject *first, CMapObject *second) {
        if (!first) {
            return false;
        }
        if (!second) {
            return true;
        }
        return first->compare(second);
    }
};

class CGameScene;
class Tile;
class Player;
class CLootProvider;
class CInteraction;

class CMap : public QObject, public std::unordered_map<Coords, std::string, CoordsHasher> {
    Q_OBJECT
  public:
    CMap(CGameScene *scene, std::string file);
    ~CMap();
    bool addTile(std::string name, int x, int y, int z);
    bool removeTile(int x, int y, int z);
    static int getTileSize();
    void move(int x, int y);
    std::string getTile(int x, int y, int z);
    bool contains(int x, int y, int z);
    void addObject(CMapObject *mapObject);
    void addRiver(int length, int startx, int starty, int startz);
    void addRoad(int length, int startx, int starty, int startz);
    void addDungeon(Coords enter, Coords exit, int width, int height);
    void removeObject(CMapObject *mapObject);
    Q_SLOT void ensureSize();
    void hide();
    CGameScene *getScene() const;
    void showAll();
    void mapUp();
    void mapDown();
    int getCurrentMap();
    std::set<CMapObject *> *getObjects();
    void loadMapFromTmx(Tmx::Map &map);
    int getEntryX();
    int getEntryY();
    int getEntryZ();
    CMapObject *getObjectByName(std::string name);
    Q_SLOT void moveCompleted();
    Q_INVOKABLE void ensureTile(int i, int j);
    std::unordered_map<Coords, Tile *, CoordsHasher> tiles;
    std::map<int, std::pair<int, int>> getBounds();
    int getCurrentXBound();
    int getCurrentYBound();
    ScriptEngine *getEngine();
    bool removeObjectByName(std::string name);
    std::string addObjectByName(std::string name, Coords coords);
    void replaceTile(std::string name, Coords coords);
    Coords getLocationByName(std::string name);
    Player *getPlayer();
    CLootProvider *getLootProvider();
    void loadingComplete();
    template <typename T> T createMapObject(std::string name) {
        return createMapObject<T>(QString::fromStdString(name));
    }
    template <typename T> std::string getClassName(QString name) {
        Json::Value config = (*CConfigurationProvider::getConfig("config/object.json"))[name.toStdString()];
        if (config.isNull()) {
            return "";
        }
        return config.get("class", std::is_same<T, CInteraction *>::value ? "CInteraction" : "").asString();
    }
    template <typename T> T createMapObject(QString name) {
        CMapObject *object = NULL;
        std::string className = getClassName<T>(name);
        if (className == "Event") className = "CEvent";
        int typeId = QMetaType::type(className.c_str());
        if (typeId) object = static_cast<CMapObject *>(QMetaType::create(typeId));
        if (object == NULL) {
            object = engine->createObject<CMapObject *>(className);
            if (!object) return NULL;
        }
        std::stringstream stream;
        stream << std::hex << (unsigned long)object;
        std::string result(stream.str());
        object->name = result;
        object->map = this;
        object->loadFromJson(name.toStdString());
        return dynamic_cast<T>(object);
    }

  private:
    std::set<CMapObject *> mapObjects;
    void randomDir(int *tab, int rule);
    CGameScene *scene;
    int currentMap = 0;
    std::map<int, std::string> defaultTiles;
    std::map<int, std::pair<int, int>> boundaries;
    int entryx, entryz, entryy;
    ScriptEngine *engine;
    CLootProvider *lootProvider;
};
