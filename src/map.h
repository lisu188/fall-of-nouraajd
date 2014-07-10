#ifndef MAP_H
#define MAP_H

#include "scriptmanager.h"

#include <list>
#include <QTimer>
#include <QObject>
#include <qgraphicsitemanimation.h>
#include <QTimeLine>
#include <src/animation.h>
#include <src/animatedobject.h>
#include <unordered_map>
#include <set>
#include <lib/json/json.h>
#include <lib/tmx/TmxMap.h>
#include <QGraphicsScene>
#include <QString>
#include <string>

class GameScene;
class MapObject;
class Tile;
class Player;
class Coords {
public:
  Coords();
  Coords(int x, int y, int z);
  int x, y, z;
  bool operator==(const Coords &other) const;
  bool operator<(const Coords &other) const;
  int getDist(Coords a);
};

struct CoordsHasher {
  std::size_t operator()(const Coords &coords) const;
};

class Map : public QObject,
            public std::unordered_map<Coords, std::string, CoordsHasher> {
  Q_OBJECT
public:
    Map(GameScene *scene, std::string file);
  ~Map();
  bool addTile(std::string name, int x, int y, int z);
  bool removeTile(int x, int y, int z);
  static int getTileSize();
  void move(int x, int y);
  std::string getTile(int x, int y, int z);
  bool contains(int x, int y, int z);
  void addObject(MapObject *mapObject);
  void addRiver(int length, int startx, int starty, int startz);
  void addRoad(int length, int startx, int starty, int startz);
  void addDungeon(Coords enter, Coords exit, int width, int height);
  void removeObject(MapObject *mapObject);
  Q_SLOT void ensureSize();
  void hide();
  GameScene *getScene() const;
  void showAll();
  void mapUp();
  void mapDown();
  int getCurrentMap();
  std::set<MapObject *> *getObjects();
  void loadMapFromTmx(Tmx::Map &map);
  int getEntryX();
  int getEntryY();
  int getEntryZ();
  MapObject *getObjectByName(std::string name);
  Q_SLOT void moveCompleted();
  Q_INVOKABLE void ensureTile(int i, int j);
  std::unordered_map<Coords, Tile *, CoordsHasher> tiles;
  std::map<int, std::pair<int, int> > getBounds();
  int getCurrentXBound();
  int getCurrentYBound();
  ScriptEngine *getEngine();

private:
  std::set<MapObject *> mapObjects;
  void randomDir(int *tab, int rule);
  GameScene *scene;
  int currentMap = 0;
  std::map<int, std::string> defaultTiles;
  std::map<int, std::pair<int, int> > boundaries;
  int entryx, entryz, entryy;
  ScriptEngine *engine;
};

class MapObject : public AnimatedObject {
  Q_OBJECT
public:
  static MapObject *createMapObject(QString name);
  MapObject();
  MapObject(int x, int y, int z, int v);
  std::string typeName;
  std::string name;
  int posx, posy, posz;
  virtual void moveTo(int x, int y, int z, bool silent = false);
  int getPosX() const;
  int getPosY() const;
  int getPosZ() const;
  void removeFromGame();
  virtual void onEnter();
  virtual void onMove();
  virtual void onCreate();
  virtual void onDestroy();
  Q_SLOT void move(int x, int y);
  virtual void loadFromJson(std::string name) = 0;
  void loadFromProps(Tmx::PropertySet set);
  virtual void setMap(Map *map);
  Map *getMap();
  void setVisible(bool vis);

protected:
  void setAnimation(std::string path);
  Map *map = 0;
  QGraphicsSimpleTextItem statsView;

public:
  void setNumber(int i, int x);
  virtual bool compare(MapObject *item);

protected:
  std::string tooltip;
  virtual void hoverEnterEvent(QGraphicsSceneHoverEvent *event);
  virtual void hoverLeaveEvent(QGraphicsSceneHoverEvent *event);
};

class Comparer {
public:
  bool operator()(MapObject *first, MapObject *second) {
    if (!first) {
      return false;
    }
    if (!second) {
      return true;
    }
    return first->compare(second);
  }
};
#endif // MAP_H
