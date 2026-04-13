#ifndef MAP_H
#define MAP_H

#include "map/coords.h"
#include "map/tiles/tile.h"
#include <QObject>
#include <QTimeLine>
#include <QTimer>
#include <animation/animatedobject.h>
#include <animation/animation.h>
#include <list>
#include <qgraphicsitemanimation.h>

class MapObject;

class Map : private std::map<Coords, Tile *> {
public:
  Map();
  ~Map();

  void move(int x, int y);

  Tile *getTile(int x, int y);
  bool contains(int x, int y);
  void addObject(MapObject *mapObject);
  bool addTile(Tile *tile);

  void addRiver(int length, int startx, int starty);
  void addRoad(int length, int startx, int starty);

  void removeObject(MapObject *mapObject);
  std::list<MapObject *> *getObjects() { return mapObjects; }

private:
  std::list<MapObject *> *mapObjects;
  void randomDir(int *tab, int rule);
};

class MapObject : public AnimatedObject {
public:
  MapObject(Map *map, int x, int y, int z);
  ~MapObject();
  int posx, posy;
  void moveTo(int x, int y);

  int getPosX() const;
  int getPosY() const;

  void removeFromGame();

  virtual void onEnter() = 0;
  virtual void onMove() = 0;

  void move(int x, int y);

  void setParentItem(QGraphicsItem *parent);

protected:
  void setAnimation(std::string path);
  Map *map;
  QGraphicsItemAnimation *animation;
  QTimeLine *timer;

  QGraphicsSimpleTextItem statsView;

public:
  std::string className;
};

#endif // MAP_H
