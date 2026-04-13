#include "map.h"

#include <algorithm>
#include <cstdlib>
#include <vector>

#include <buildings/cave.h>
#include <creatures/players/player.h>
#include <map/tiles/groundtile.h>
#include <map/tiles/mountaintile.h>
#include <map/tiles/roadtile.h>
#include <map/tiles/watertile.h>
#include <view/gamescene.h>

Map::Map() { mapObjects = new std::list<MapObject *>(); }

Map::~Map() {
  std::vector<Tile *> tilesToDelete;
  for (iterator it = begin(); it != end(); ++it) {
    tilesToDelete.push_back((*it).second);
  }
  clear();

  for (std::vector<Tile *>::iterator it = tilesToDelete.begin();
       it != tilesToDelete.end(); ++it) {
    if ((*it)->scene())
      (*it)->scene()->removeItem(*it);
    delete *it;
  }

  std::vector<MapObject *> objects(mapObjects->begin(), mapObjects->end());
  mapObjects->clear();
  delete mapObjects;

  for (std::vector<MapObject *>::iterator it = objects.begin();
       it != objects.end(); ++it) {
    if ((*it)->scene())
      (*it)->scene()->removeItem(*it);
    delete *it;
  }
}

void Map::move(int x, int y) {
  Player *player = GameScene::getPlayer();
  if (!player)
    return;
  player->move(x, y);
}

Tile *Map::getTile(int x, int y) {
  iterator it = find(Coords(x, y));
  if (it == end())
    return 0;
  return (*it).second;
}

bool Map::contains(int x, int y) { return getTile(x, y) != 0; }

void Map::addObject(MapObject *mapObject) {
  if (!mapObject)
    return;
  mapObjects->push_back(mapObject);
  mapObject->moveTo(mapObject->getPosX(), mapObject->getPosY());
  if (GameScene::getGame() && mapObject->scene() != GameScene::getGame()) {
    GameScene::getGame()->addItem(mapObject);
  }
}

void Map::addRiver(int length, int startx, int starty) {
  int x = startx;
  int y = starty;
  for (int i = 0; i < length; ++i) {
    addTile(new WaterTile(x, y));
    switch (rand() % 4) {
    case 0:
      x++;
      break;
    case 1:
      x--;
      break;
    case 2:
      y++;
      break;
    default:
      y--;
      break;
    }
  }
}

void Map::addRoad(int length, int startx, int starty) {
  int x = startx;
  int y = starty;
  for (int i = 0; i < length; ++i) {
    addTile(new RoadTile(x, y));
    if (rand() % 2 == 0)
      x += rand() % 2 == 0 ? 1 : -1;
    else
      y += rand() % 2 == 0 ? 1 : -1;
  }
}

void Map::removeObject(MapObject *mapObject) {
  if (!mapObject)
    return;
  mapObjects->remove(mapObject);
  if (mapObject->scene())
    mapObject->scene()->removeItem(mapObject);
  delete mapObject;
}

void Map::randomDir(int *tab, int) {
  tab[0] = 0;
  tab[1] = 1;
  tab[2] = 2;
  tab[3] = 3;
  for (int i = 0; i < 4; ++i) {
    int j = rand() % 4;
    std::swap(tab[i], tab[j]);
  }
}

bool Map::addTile(Tile *tile) {
  if (!tile)
    return false;
  if (contains(tile->getCoords().first, tile->getCoords().second)) {
    delete tile;
    return false;
  }

  insert(std::pair<Coords, Tile *>(tile->getCoords(), tile));
  tile->addToGame();
  return true;
}

MapObject::MapObject(Map *map, int x, int y, int z) {
  this->map = map;
  posx = x;
  posy = y;
  animation = 0;
  timer = 0;
  setZValue(z);
  statsView.setParentItem(this);
  statsView.setVisible(false);
  setPos(x * Tile::size, y * Tile::size);
}

MapObject::~MapObject() {
  if (timer)
    delete timer;
  if (animation)
    delete animation;
}

void MapObject::moveTo(int x, int y) {
  posx = x;
  posy = y;
  setPos(x * Tile::size, y * Tile::size);
}

int MapObject::getPosX() const { return posx; }

int MapObject::getPosY() const { return posy; }

void MapObject::removeFromGame() {
  Map *owner = map;
  map = 0;
  if (owner) {
    owner->removeObject(this);
  }
}

void MapObject::move(int x, int y) {
  if (!map)
    return;

  Tile *destination = map->getTile(posx + x, posy + y);
  if (!destination || !destination->canStep())
    return;

  moveTo(posx + x, posy + y);
  destination->onStep();

  std::vector<MapObject *> collisions;
  for (std::list<MapObject *>::iterator it = map->getObjects()->begin();
       it != map->getObjects()->end(); ++it) {
    if (*it != this && (*it)->getPosX() == posx && (*it)->getPosY() == posy) {
      collisions.push_back(*it);
    }
  }

  onMove();

  for (std::vector<MapObject *>::iterator it = collisions.begin();
       it != collisions.end(); ++it) {
    if (*it && (*it)->getPosX() == posx && (*it)->getPosY() == posy) {
      (*it)->onEnter();
    }
  }
}

void MapObject::setParentItem(QGraphicsItem *parent) {
  QGraphicsItem::setParentItem(parent);
}

void MapObject::setAnimation(std::string path) {
  AnimatedObject::setAnimation(path);
}
