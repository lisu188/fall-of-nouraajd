#include "map.h"
#include <src/pathfinder.h>

#include <src/map.h>
#include "tile.h"

#include <src/building.h>
#include <lib/tmx/Tmx.h>
#include <src/configurationprovider.h>
#include <src/monster.h>
#include <src/player.h>
#include <src/interaction.h>
#include <src/item.h>
#include <src/gamescene.h>
#include <src/gameview.h>

#include <QApplication>
#include <QFile>
#include <QDesktopWidget>
#include <QGraphicsSceneMouseEvent>
#include <QMetaType>
#include <QWidget>
#include <algorithm>
#include <cstdlib>
#include <vector>
#include <math.h>
#include <src/playerstatsview.h>
#include <src/playerlistview.h>

namespace {

int tile_size = 50;
const int animation_step_ms = 100;

bool contains_object(std::list<MapObject *> *objects, MapObject *object) {
  return std::find(objects->begin(), objects->end(), object) != objects->end();
}

} // namespace

// The map now loads its own Tiled file, as the scene's startGame did before.
Map::Map(QGraphicsScene *scene, std::string file) : scene(dynamic_cast<GameScene *>(scene)) {
  connect(CompletionListener::getInstance(), SIGNAL(completed()), this,
          SLOT(moveCompleted()));
  defaultTiles[0] = "GrassTile";
  Tmx::Map tmxMap;
  QFile source(file.c_str());
  source.open(QIODevice::ReadOnly);
  QByteArray data = source.readAll();
  std::string dataString = data.data();
  tmxMap.ParseText(dataString);
  source.close();
  loadMapFromTmx(tmxMap);
}

Map::~Map() {
  std::vector<Tile *> tile_list;
  for (std::unordered_map<Coords, Tile *, CoordsHasher>::iterator it = tiles.begin(); it != tiles.end();
       ++it) {
    tile_list.push_back((*it).second);
  }
  tiles.clear();
  clear();
  for (std::vector<Tile *>::iterator it = tile_list.begin();
       it != tile_list.end(); ++it) {
    if ((*it)->scene()) {
      (*it)->scene()->removeItem(*it);
    }
    delete *it;
  }

  std::vector<MapObject *> objects(mapObjects.begin(), mapObjects.end());
  mapObjects.clear();
  for (std::vector<MapObject *>::iterator it = objects.begin();
       it != objects.end(); ++it) {
    if ((*it)->scene()) {
      (*it)->scene()->removeItem(*it);
    }
    delete *it;
  }
}

bool Map::addTile(std::string name, int x, int y, int z) {
  Coords coords(x, y, z);
  std::unordered_map<Coords, Tile *, CoordsHasher>::iterator existing = tiles.find(coords);
  if (existing != tiles.end()) {
    if (existing->second && existing->second->typeName.compare(name) == 0) {
      return true;
    }
    if (existing->second && existing->second->scene()) {
      existing->second->scene()->removeItem(existing->second);
    }
    delete existing->second;
    tiles.erase(existing);
    std::unordered_map<Coords, std::string, CoordsHasher>::iterator map_it =
        find(coords);
    if (map_it != end()) {
      erase(map_it);
    }
  }

  Tile *tile = Tile::getTile(name, x, y, z);
  if (!tile) {
    return false;
  }
  tile->MapObject::setMap(this);
  tile->moveTo(x, y, z, true);
  tile->QGraphicsItem::setVisible(z == currentMap);
  tiles.insert(std::pair<Coords, Tile *>(coords, tile));
  insert(std::pair<Coords, std::string>(coords, name));
  return true;
}

int Map::getTileSize() { return tile_size; }


void Map::move(int x, int y) {
  Player *player = scene->getPlayer();
  if (!player) {
    showAll();
    return;
  }

  currentMap = player->getPosZ();
  ensureSize();

  const int next_x = player->getPosX() + x;
  const int next_y = player->getPosY() + y;
  const int next_z = player->getPosZ();
  const bool moving = x != 0 || y != 0;

  if (moving) {
    if (tiles.find(Coords(next_x, next_y, next_z)) == tiles.end()) {
      std::string tile_name = getTile(next_x, next_y, next_z);
      if (tile_name.compare("") != 0) {
        addTile(tile_name, next_x, next_y, next_z);
      }
    }

    std::unordered_map<Coords, Tile *, CoordsHasher>::iterator tile_it =
        tiles.find(Coords(next_x, next_y, next_z));
    if (tile_it == tiles.end() || !tile_it->second->canStep()) {
      return;
    }

    player->moveTo(next_x, next_y, next_z);
    player->onMove();
  }

  currentMap = player->getPosZ();
  ensureSize();
  player->getEntered()->clear();

  Coords player_coords(player->getPosX(), player->getPosY(), player->getPosZ());
  std::vector<MapObject *> objects(mapObjects.begin(), mapObjects.end());
  for (std::vector<MapObject *>::iterator it = objects.begin();
       it != objects.end(); ++it) {
    MapObject *object = *it;
    if (!object || object == player) {
      continue;
    }
    if (object->getPosX() == player_coords.x &&
        object->getPosY() == player_coords.y &&
        object->getPosZ() == player_coords.z) {
      player->addEntered(object);
    }
  }

  std::unordered_map<Coords, Tile *, CoordsHasher>::iterator current_tile = tiles.find(player_coords);
  if (current_tile != tiles.end()) {
    current_tile->second->onStep();
  }

  objects.assign(mapObjects.begin(), mapObjects.end());
  for (std::vector<MapObject *>::iterator it = objects.begin();
       it != objects.end(); ++it) {
    MapObject *object = *it;
    if (!object || object == player ||
        contains_object(player->getEntered(), object)) {
      continue;
    }
    object->onMove();
  }

  objects.assign(mapObjects.begin(), mapObjects.end());
  for (std::vector<MapObject *>::iterator it = objects.begin();
       it != objects.end(); ++it) {
    MapObject *object = *it;
    if (!object || object == player ||
        contains_object(player->getEntered(), object)) {
      continue;
    }
    if (object->getPosX() == player->getPosX() &&
        object->getPosY() == player->getPosY() &&
        object->getPosZ() == player->getPosZ()) {
      player->addEntered(object);
    }
  }

  showAll();
  if (scene->getView()) {
    scene->getView()->centerOn(player);
  }

  CompletionListener::getInstance()->start();
  CompletionListener::getInstance()->run();
}

// Entered objects and fights are handled once every monster's path search has completed.
void Map::moveCompleted() {
  CompletionListener::getInstance()->stop();
  Player *player = scene->getPlayer();
  if (!player) {
    return;
  }
  std::list<MapObject *> entered(*player->getEntered());
  for (std::list<MapObject *>::iterator it = entered.begin();
       it != entered.end(); ++it) {
    (*it)->onEnter();
    if (scene->getPlayer() != player) {
      return;
    }
  }
  player->getEntered()->clear();
  if (scene->getView() && player->getFightList()->size() > 0) {
    scene->getView()->showFightView();
  }
}

std::string Map::getTile(int x, int y, int z) {
  std::unordered_map<Coords, std::string, CoordsHasher>::iterator it =
      find(Coords(x, y, z));
  if (it != end()) {
    return (*it).second;
  }
  if (defaultTiles.find(z) != defaultTiles.end()) {
    return defaultTiles[z];
  }
  return "";
}

std::set<MapObject *> *Map::getObjects() { return &mapObjects; }

bool Map::removeTile(int x, int y, int z) {
  Coords coords(x, y, z);
  std::unordered_map<Coords, Tile *, CoordsHasher>::iterator existing = tiles.find(coords);
  if (existing == tiles.end()) {
    return false;
  }
  if (existing->second && existing->second->scene()) {
    existing->second->scene()->removeItem(existing->second);
  }
  delete existing->second;
  tiles.erase(existing);
  return true;
}

int Map::getEntryX() { return entryx; }

int Map::getEntryY() { return entryy; }

int Map::getEntryZ() { return entryz; }

MapObject *Map::getObjectByName(std::string name) {
  for (std::set<MapObject *>::iterator it = mapObjects.begin();
       it != mapObjects.end(); ++it) {
    if ((*it)->name.compare(name) == 0) {
      return *it;
    }
  }
  return 0;
}

// Creates the tile at (i, j) on the current level when it is not loaded yet.
void Map::ensureTile(int i, int j) {
  if (tiles.find(Coords(i, j, currentMap)) == tiles.end()) {
    std::string name = getTile(i, j, currentMap);
    if (name.compare("") != 0) {
      addTile(name, i, j, currentMap);
    }
  }
}

bool Map::contains(int x, int y, int z) {
  return getTile(x, y, z).compare("") != 0;
}

void Map::addObject(MapObject *mapObject) {
  if (!mapObject) {
    return;
  }
  mapObjects.insert(mapObject);
  mapObject->setMap(this);
  if (mapObject->inherits("Player")) {
    scene->setPlayer((Player *)mapObject);
    currentMap = mapObject->getPosZ();
  }
  mapObject->onCreate();
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

void Map::addRiver(int length, int startx, int starty, int startz) {
  int x = startx;
  int y = starty;
  for (int i = 0; i < length; ++i) {
    addTile("WaterTile", x, y, startz);
    int dirs[4];
    randomDir(dirs, i);
    switch (dirs[0]) {
    case 0:
      ++x;
      break;
    case 1:
      --x;
      break;
    case 2:
      ++y;
      break;
    default:
      --y;
      break;
    }
  }
}

void Map::addRoad(int length, int startx, int starty, int startz) {
  int x = startx;
  int y = starty;
  for (int i = 0; i < length; ++i) {
    addTile("RoadTile", x, y, startz);
    if (rand() % 2 == 0) {
      x += rand() % 2 == 0 ? 1 : -1;
    } else {
      y += rand() % 2 == 0 ? 1 : -1;
    }
  }
}

void Map::addDungeon(Coords enter, Coords exit, int width, int height) {
  for (int x = 0; x < width; ++x) {
    for (int y = 0; y < height; ++y) {
      addTile("GroundTile", exit.x + x, exit.y + y, exit.z);
    }
  }
}

void Map::removeObject(MapObject *mapObject) {
  if (!mapObject) {
    return;
  }
  mapObject->onDestroy();
  mapObjects.erase(mapObject);
  if (scene->getPlayer()) {
    scene->getPlayer()->getEntered()->remove(mapObject);
  }
  if (mapObject->scene()) {
    mapObject->scene()->removeItem(mapObject);
  }
  delete mapObject;
}

void Map::ensureSize() {
  Player *player = scene->getPlayer();
  if (!player || defaultTiles.find(player->getPosZ()) == defaultTiles.end()) {
    return;
  }

  int size_x = 20;
  int size_y = 15;
  if (scene->getView()) {
    size_x = scene->getView()->width() / getTileSize() + 2;
    size_y = scene->getView()->height() / getTileSize() + 2;
  } else {
    size_x = QApplication::desktop()->width() / getTileSize() + 2;
    size_y = QApplication::desktop()->height() / getTileSize() + 2;
  }

  for (int x = player->getPosX() - size_x; x <= player->getPosX() + size_x;
       ++x) {
    for (int y = player->getPosY() - size_y; y <= player->getPosY() + size_y;
         ++y) {
      if (tiles.find(Coords(x, y, player->getPosZ())) == tiles.end()) {
        const std::string background = defaultTiles[player->getPosZ()];
        addTile(background.empty() ? "GrassTile" : background, x, y, player->getPosZ());
      }
    }
  }
}

void Map::hide() {
  for (std::unordered_map<Coords, Tile *, CoordsHasher>::iterator it = tiles.begin(); it != tiles.end();
       ++it) {
    if ((*it).second) {
      (*it).second->QGraphicsItem::setVisible(false);
    }
  }
  for (std::set<MapObject *>::iterator it = mapObjects.begin();
       it != mapObjects.end(); ++it) {
    if (*it) {
      (*it)->QGraphicsItem::setVisible(false);
    }
  }
}

// The map is authored in Tiled: map properties hold the entry, tile properties name the
// terrain type, and each object's type names the configured object it places.
void Map::loadMapFromTmx(Tmx::Map &map) {
  const Tmx::PropertySet &properties = map.GetProperties();
  entryx = properties.GetNumericProperty("x");
  entryy = properties.GetNumericProperty("y");
  entryz = properties.GetNumericProperty("z");
  for (int i = 0; i < map.GetNumLayers(); ++i) {
    const Tmx::Layer *layer = map.GetLayer(i);
    int z = layer->GetProperties().HasProperty("z")
                ? layer->GetProperties().GetNumericProperty("z")
                : 0;
    // Each level is bounded by its layer unless the layer names explicit bounds.
    boundaries[z] = std::make_pair(
        layer->GetProperties().HasProperty("xBound") ? layer->GetProperties().GetNumericProperty("xBound")
                                                      : layer->GetWidth() - 1,
        layer->GetProperties().HasProperty("yBound") ? layer->GetProperties().GetNumericProperty("yBound")
                                                      : layer->GetHeight() - 1);
    for (int x = 0; x < layer->GetWidth(); ++x) {
      for (int y = 0; y < layer->GetHeight(); ++y) {
        int tileset_index = layer->GetTileTilesetIndex(x, y);
        if (tileset_index < 0) {
          continue;
        }
        const Tmx::Tile *tile =
            map.GetTileset(tileset_index)->GetTile(layer->GetTileId(x, y));
        if (!tile) {
          continue;
        }
        std::string type = tile->GetProperties().GetLiteralProperty("type");
        if (type.compare("") != 0) {
          (*this)[Coords(x, y, z)] = type;
        }
      }
    }
  }
  for (int i = 0; i < map.GetNumObjectGroups(); ++i) {
    const Tmx::ObjectGroup *group = map.GetObjectGroup(i);
    for (int j = 0; j < group->GetNumObjects(); ++j) {
      const Tmx::Object *source = group->GetObject(j);
      MapObject *object = MapObject::createMapObject(QString::fromStdString(source->GetType()));
      if (!object) {
        continue;
      }
      object->name = source->GetName();
      object->loadFromProps(source->GetProperties());
      object->moveTo(source->GetX() / map.GetTileWidth(),
                     source->GetY() / map.GetTileHeight(), 0, true);
      addObject(object);
    }
  }
}

GameScene *Map::getScene() const { return scene; }

std::map<int, std::pair<int, int> > Map::getBounds() { return boundaries; }

void Map::showAll() {
  for (std::unordered_map<Coords, Tile *, CoordsHasher>::iterator it = tiles.begin(); it != tiles.end();
       ++it) {
    Tile *tile = (*it).second;
    if (!tile) {
      continue;
    }
    if (tile->scene() != scene) {
      scene->addItem(tile);
    }
    tile->setPos(tile->getPosX() * getTileSize(),
                 tile->getPosY() * getTileSize());
    tile->QGraphicsItem::setVisible(tile->getPosZ() == currentMap);
  }

  for (std::set<MapObject *>::iterator it = mapObjects.begin();
       it != mapObjects.end(); ++it) {
    MapObject *object = *it;
    if (!object) {
      continue;
    }
    if (object->parentItem() == 0 && object->scene() != scene) {
      scene->addItem(object);
    }
    if (object->parentItem() == 0) {
      object->setPos(object->getPosX() * getTileSize(),
                     object->getPosY() * getTileSize());
    }
    object->QGraphicsItem::setVisible(object->getPosZ() == currentMap);
  }
}

void Map::mapUp() { ++currentMap; }

void Map::mapDown() { --currentMap; }

int Map::getCurrentMap() { return currentMap; }


// Every object is described in config/object.json; its "class" names the type to create.
MapObject *MapObject::createMapObject(QString name) {
  Json::Value config = (*ConfigurationProvider::getConfig("config/object.json"))[name.toStdString()];
  if (config.isNull()) {
    return NULL;
  }
  int typeId = QMetaType::type(config.get("class", "").asString().c_str());
  if (typeId == 0) {
    return NULL;
  }
  MapObject *object = (MapObject *)QMetaType::create(typeId);
  object->loadFromJson(name.toStdString());
  return object;
}

// Tiled object properties set the object's Qt properties of the same name.
void MapObject::loadFromProps(Tmx::PropertySet set) {
  std::map<std::string, std::string> properties = set.GetList();
  for (std::map<std::string, std::string>::iterator it = properties.begin();
       it != properties.end(); ++it) {
    setProperty(it->first.c_str(), QVariant(QString::fromStdString(it->second)));
  }
}

MapObject::MapObject() : MapObject(0, 0, 0, 0) {}


MapObject::MapObject(int x, int y, int z, int v) {
  posx = x;
  posy = y;
  posz = z;
  setZValue(v);
  setAcceptHoverEvents(true);
  statsView.setParentItem(this);
  statsView.setVisible(false);
}

void MapObject::moveTo(int x, int y, int z, bool silent) {
  posx = x;
  posy = y;
  posz = z;
  QPointF to(x * Map::getTileSize(), y * Map::getTileSize());

  setPos(to);

  if (map) {
    QGraphicsItem::setVisible(posz == map->getCurrentMap());
  }

  if (!silent && map) {
    Player *player = map->getScene()->getPlayer();
    if (player && player != this && player->getPosX() == posx &&
        player->getPosY() == posy && player->getPosZ() == posz) {
      player->addEntered(this);
    }
  }
}

int MapObject::getPosX() const { return posx; }

int MapObject::getPosY() const { return posy; }

int MapObject::getPosZ() const { return posz; }

void MapObject::removeFromGame() {
  if (map) {
    Map *owner = map;
    map = 0;
    owner->removeObject(this);
  }
}

void MapObject::move(int x, int y) {
  if (!map) {
    return;
  }

  int next_x = posx + x;
  int next_y = posy + y;
  int next_z = posz;
  std::string tile_name = map->getTile(next_x, next_y, next_z);
  if (tile_name.compare("") == 0) {
    return;
  }

  Tile *tile = Tile::getTile(tile_name, next_x, next_y, next_z);
  bool can_step = tile && tile->canStep();
  delete tile;
  if (!can_step) {
    return;
  }

  moveTo(next_x, next_y, next_z);
}

void MapObject::setMap(Map *map) {
  this->map = map;
  if (!map) {
    return;
  }
  if (scene() != map->getScene()) {
    map->getScene()->addItem(this);
  }
  setPos(posx * Map::getTileSize(), posy * Map::getTileSize());
  QGraphicsItem::setVisible(posz == map->getCurrentMap());
}

Map *MapObject::getMap() { return map; }

void MapObject::setVisible(bool vis) { QGraphicsItem::setVisible(vis); }

// Objects without a script react to nothing by default.
void MapObject::onEnter() {}

void MapObject::onMove() {}

void MapObject::onCreate() {}

void MapObject::onDestroy() {}

void MapObject::setAnimation(std::string path) {
  AnimatedObject::setAnimation(path, Map::getTileSize());
}

// ---- formerly coords.cpp ----
Coords::Coords()
{
    x = y = z = 0;
}

Coords::Coords(int x, int y, int z): x(x), y(y), z(z) {}

bool Coords::operator==(const Coords &other) const
{
    return (x == other.x && y == other.y && z == other.z);
}

bool Coords::operator<(const Coords &other) const
{
    if (x < other.x) {
        return true;
    }
    if (y < other.y && x == other.x) {
        return true;
    }
    if (z < other.z && x == other.x && y == other.y) {
        return true;
    }
    return false;
}

int Coords::getDist(Coords a)
{
    double x = this->x - a.x;
    x *= x;
    double y = this->y - a.y;
    y *= y;
    return sqrt(x + y);
}

std::size_t CoordsHasher::operator()(const Coords &coords) const
{
    using std::size_t;
    int a = (size_t)coords.x;
    int b = (size_t)coords.y;
    int c = (size_t)coords.z;
    return (size_t)(a ^ b) ^ (b ^ c) ^ (a ^ c);
}

