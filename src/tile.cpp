#include "tile.h"

#include <src/gamescene.h>
#include <src/configurationprovider.h>
#include <src/destroyer.h>

std::unordered_map<std::string, std::function<void()> > Tile::steps{
  { "RoadTile", &RoadTile }
};

Tile::Tile(std::string name, int x, int y, int z) : ListItem(x, y, z, 1) {
  setXYZ(x, y, z);
  loadFromJson(name);
}

Tile::Tile() {}

Tile::Tile(const Tile &tile)
    : Tile(tile.typeName, tile.getPosX(), tile.getPosY(), tile.getPosZ()) {}

Tile::~Tile() {}

void Tile::moveTo(int x, int y, int z, bool silent) {
  if (init && map) {
    if (map->find(Coords(posx, posy, posz)) != map->end()) {
      map->erase(map->find(Coords(posx, posy, posz)));
    }
    setXYZ(x, y, z);
    map->insert(
        std::pair<Coords, std::string>(Coords(posx, posy, posz), typeName));
  }
  MapObject::moveTo(x, y, z, silent);
  init = true;
}

Coords Tile::getCoords() { return Coords(posx, posy, posz); }

void Tile::onStep() {
  if (steps.find(typeName) != steps.end()) {
    steps[typeName]();
  }
}

bool Tile::canStep() const { return step; }

Tile *Tile::getTile(std::string type, int x, int y, int z) {
  return new Tile(type, x, y, z);
}

void Tile::addToScene(QGraphicsScene *scene) {
  setPos(posx * Map::getTileSize(), posy * Map::getTileSize());
  MapObject::setMap(dynamic_cast<GameScene *>(scene)->getMap());
}

void Tile::removeFromScene(QGraphicsScene *scene) { scene->removeItem(this); }

void Tile::loadFromJson(std::string name) {
  this->typeName = name;
  Json::Value config =
      (*ConfigurationProvider::getConfig("config/tiles.json"))[typeName];
  step = config.get("canStep", true).asBool();
  setAnimation(config.get("path", "").asCString());
}

void Tile::setDraggable() { draggable = true; }

void Tile::setXYZ(int x, int y, int z) {
  posx = x;
  posy = y;
  posz = z;
}

void Tile::mousePressEvent(QGraphicsSceneMouseEvent *event) {
  if (draggable) {
    AnimatedObject::mousePressEvent(event);
  }
  event->setAccepted(draggable);
}

bool Tile::canSave() { return false; }

void Tile::setMap(Map *map) {
  this->map = map;
  addToScene(map->getScene());
}

//void RoadTile() { GameScene::getPlayer()->heal(1); }
