#include "map.h"

#include "playeranimation.h"
#include "tile.h"

#include <buildings/dungeon.h>
#include <configuration/configurationprovider.h>
#include <creatures/monster.h>
#include <creatures/player.h>
#include <interactions/interaction.h>
#include <items/item.h>
#include <view/gamescene.h>
#include <view/gameview.h>

#include <QApplication>
#include <QDesktopWidget>
#include <QGraphicsSceneMouseEvent>
#include <QMetaType>
#include <QWidget>
#include <algorithm>
#include <cstdlib>
#include <vector>
#include <QDebug>
#include <tmx/TmxLayer.h>
#include <tmx/TmxTileset.h>
#include <tmx/TmxTile.h>
#include <tmx/TmxObject.h>
#include <tmx/TmxObjectGroup.h>

namespace {

int tile_size = 50;
const int animation_step_ms = 100;

Json::Value to_coords_json(int x, int y, int z) {
  Json::Value entry;
  entry[(unsigned int)0] = x;
  entry[(unsigned int)1] = y;
  entry[(unsigned int)2] = z;
  return entry;
}

MapObject *create_object(const std::string &type_name,
                         const std::string &class_name, Json::Value config) {
  if (type_name == "Player") {
    return new Player(class_name, config);
  }
  if (type_name == "Monster" || type_name == "Creature") {
    return new Monster(class_name, config);
  }
  if (type_name == "Interaction") {
    Interaction *interaction = Interaction::getInteraction(class_name);
    if (interaction) {
      interaction->loadFromJson(config);
    }
    return interaction;
  }
  if (type_name == "Item" || type_name == "Weapon" || type_name == "Armor" ||
      type_name == "Potion" || type_name == "SmallWeapon" ||
      type_name == "Helmet" || type_name == "Boots" || type_name == "Belt" ||
      type_name == "Gloves") {
    Item *item = Item::getItem(class_name);
    if (item) {
      item->moveTo(config.get((unsigned int)0, 0).asInt(),
                   config.get((unsigned int)1, 0).asInt(),
                   config.get((unsigned int)2, 0).asInt(), true);
    }
    return item;
  }

  int type_id = QMetaType::type(type_name.c_str());
  if (type_id == QMetaType::UnknownType) {
    type_id = QMetaType::type(class_name.c_str());
  }
  if (type_id == QMetaType::UnknownType) {
    return 0;
  }

  MapObject *object = (MapObject *)QMetaType::create(type_id);
  if (object) {
    if (object->className.compare("") == 0) {
      object->className = class_name;
    }
    object->loadFromJson(config);
  }
  return object;
}

bool contains_object(std::list<MapObject *> *objects, MapObject *object) {
  return std::find(objects->begin(), objects->end(), object) != objects->end();
}

} // namespace

Map::Map(QGraphicsScene *scene) : scene(scene), entryx(0), entryz(0), entryy(0) {
  defaultTiles[0] = "GrassTile";
}

Map::~Map() {
  std::vector<Tile *> tile_list;
  for (std::map<Coords, Tile *>::iterator it = tiles.begin(); it != tiles.end();
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
  std::map<Coords, Tile *>::iterator existing = tiles.find(coords);
  if (existing != tiles.end()) {
    if (existing->second && existing->second->className.compare(name) == 0) {
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


bool Map::isEditor() {
  return GameScene::getGame() == 0 || GameScene::getView() == 0;
}

void Map::move(int x, int y) {
  Player *player = GameScene::getPlayer();
  if (!player) {
    showAll();
    return;
  }

  currentMap = player->getPosZ();
  ensureSize(player);

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

    std::map<Coords, Tile *>::iterator tile_it =
        tiles.find(Coords(next_x, next_y, next_z));
    if (tile_it == tiles.end() || !tile_it->second->canStep()) {
      return;
    }

    player->moveTo(next_x, next_y, next_z);
    player->onMove();
  }

  currentMap = player->getPosZ();
  ensureSize(player);
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

  std::map<Coords, Tile *>::iterator current_tile = tiles.find(player_coords);
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
  if (GameScene::getView()) {
    GameScene::getView()->centerOn(player);
  }

  if (!moving || !GameScene::getView()) {
    std::list<MapObject *> entered(*player->getEntered());
    for (std::list<MapObject *>::iterator it = entered.begin();
         it != entered.end(); ++it) {
      (*it)->onEnter();
      if (GameScene::getPlayer() != player) {
        return;
      }
    }
    player->getEntered()->clear();
    if (GameScene::getView() && player->getFightList()->size() > 0) {
      GameScene::getView()->showFightView();
    }
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
    GameScene::setPlayer((Player *)mapObject);
    currentMap = mapObject->getPosZ();
  }
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

  Json::Value enter_config = to_coords_json(enter.x, enter.y, enter.z);
  enter_config[(unsigned int)3] = exit.x;
  enter_config[(unsigned int)4] = exit.y;
  enter_config[(unsigned int)5] = exit.z;
  Dungeon *entrance = new Dungeon();
  entrance->loadFromJson(enter_config);
  addObject(entrance);

  Json::Value exit_config = to_coords_json(exit.x, exit.y, exit.z);
  exit_config[(unsigned int)3] = enter.x;
  exit_config[(unsigned int)4] = enter.y;
  exit_config[(unsigned int)5] = enter.z;
  Dungeon *return_gate = new Dungeon();
  return_gate->loadFromJson(exit_config);
  addObject(return_gate);
}

void Map::removeObject(MapObject *mapObject) {
  if (!mapObject) {
    return;
  }
  mapObjects.erase(mapObject);
  if (GameScene::getPlayer()) {
    GameScene::getPlayer()->getEntered()->remove(mapObject);
  }
  if (mapObject->scene()) {
    mapObject->scene()->removeItem(mapObject);
  }
  delete mapObject;
}

void Map::loadMapFromJson(Json::Value config) {
  if (config.isNull()) {
    return;
  }

  defaultTiles.clear();
  Json::Value defaults = config["default"];
  Json::Value::iterator default_it = defaults.begin();
  for (; default_it != defaults.end(); ++default_it) {
    defaultTiles[atoi(default_it.memberName())] = (*default_it).asString();
  }
  if (defaultTiles.size() == 0) {
    defaultTiles[0] = "GrassTile";
  }

  Json::Value::iterator it = config.begin();
  for (; it != config.end(); ++it) {
    std::string tile_name = it.memberName();
    if (tile_name.compare("default") == 0) {
      continue;
    }
    for (unsigned int i = 0; i < (*it).size(); ++i) {
      Json::Value entry = (*it)[i];
      addTile(tile_name, entry.get((unsigned int)0, 0).asInt(),
              entry.get((unsigned int)1, 0).asInt(),
              entry.get((unsigned int)2, 0).asInt());
    }
  }
}

Json::Value Map::saveMapToJson() {
  Json::Value config;
  for (std::map<int, std::string>::iterator it = defaultTiles.begin();
       it != defaultTiles.end(); ++it) {
    config["default"][std::to_string((*it).first).c_str()] = (*it).second;
  }

  for (std::map<Coords, Tile *>::iterator it = tiles.begin(); it != tiles.end();
       ++it) {
    Tile *tile = (*it).second;
    if (!tile) {
      continue;
    }
    config[tile->className.c_str()].append(
        to_coords_json(tile->getPosX(), tile->getPosY(), tile->getPosZ()));
  }
  return config;
}

void Map::loadFromJson(Json::Value config) {
  if (config.isNull()) {
    return;
  }

  if (config["gameSize"].isInt()) {
    tile_size = config["gameSize"].asInt() > 0 ? config["gameSize"].asInt() : 50;
  }

  loadMapFromJson(config["map"].isObject() ? config["map"] : config);
  GameScene::setPlayer(0);
  loadStateFromJson(config["state"]);

  if (GameScene::getPlayer()) {
    currentMap = GameScene::getPlayer()->getPosZ();
  }
  showAll();
}

Json::Value Map::saveToJson() {
  Json::Value config;
  config["gameSize"] = getTileSize();
  config["map"] = saveMapToJson();
  config["state"] = saveStateToJson();
  return config;
}

void Map::ensureSize(Player *player) {
  if (!player || defaultTiles.find(player->getPosZ()) == defaultTiles.end()) {
    return;
  }

  int size_x = 20;
  int size_y = 15;
  if (GameScene::getView()) {
    size_x = GameScene::getView()->width() / getTileSize() + 2;
    size_y = GameScene::getView()->height() / getTileSize() + 2;
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
  for (std::map<Coords, Tile *>::iterator it = tiles.begin(); it != tiles.end();
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

Json::Value Map::saveStateToJson() {
  Json::Value config;
  for (std::set<MapObject *>::iterator it = mapObjects.begin();
       it != mapObjects.end(); ++it) {
    MapObject *object = *it;
    if (!object || !object->canSave()) {
      continue;
    }
    config[object->metaObject()->className()][object->className.c_str()].append(
        object->saveToJson());
  }
  return config;
}

void Map::loadStateFromJson(Json::Value config) {
  if (config.isNull()) {
    return;
  }

  Json::Value::iterator type_it = config.begin();
  for (; type_it != config.end(); ++type_it) {
    std::string type_name = type_it.memberName();
    Json::Value::iterator class_it = (*type_it).begin();
    for (; class_it != (*type_it).end(); ++class_it) {
      std::string class_name = class_it.memberName();
      for (unsigned int i = 0; i < (*class_it).size(); ++i) {
        MapObject *object =
            create_object(type_name, class_name, (*class_it)[i]);
        if (!object) {
          continue;
        }
        addObject(object);
      }
    }
  }
}

QGraphicsScene *Map::getScene() const { return scene; }

void Map::showAll() {
  for (std::map<Coords, Tile *>::iterator it = tiles.begin(); it != tiles.end();
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

MapObject::~MapObject() {
  if (timer) {
    timer->stop();
    delete timer;
  }
  if (animation) {
    delete animation;
  }
}

void MapObject::moveTo(int x, int y, int z, bool silent) {
  QPointF from = QGraphicsItem::pos();
  posx = x;
  posy = y;
  posz = z;
  QPointF to(x * Map::getTileSize(), y * Map::getTileSize());

  if (timer) {
    timer->stop();
    delete timer;
    timer = 0;
  }
  if (animation) {
    delete animation;
    animation = 0;
  }

  if (!silent && map && GameScene::getView() && from != to) {
    if (inherits("Player")) {
      animation = new PlayerAnimation();
    } else {
      animation = new QGraphicsItemAnimation();
    }
    timer = new QTimeLine(animation_step_ms);
    animation->setItem(this);
    animation->setTimeLine(timer);
    animation->setPosAt(0, from);
    animation->setPosAt(1, to);
    timer->start();
  } else {
    setPos(to);
  }

  if (map) {
    QGraphicsItem::setVisible(posz == map->getCurrentMap());
  }

  if (!silent) {
    Player *player = GameScene::getPlayer();
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

void MapObject::mousePressEvent(QGraphicsSceneMouseEvent *event) {
  if (Map::isEditor()) {
    AnimatedObject::mousePressEvent(event);
    event->accept();
    return;
  }
  event->ignore();
}

void MapObject::setAnimation(std::string path) {
  AnimatedObject::setAnimation(path, Map::getTileSize());
}

void Map::loadMapFromTmx(Tmx::Map &source) {
    if (source.HasError()) qFatal("TMX reconstruction could not parse the authored map");
    entryx = source.GetProperties().GetNumericProperty("x");
    entryy = source.GetProperties().GetNumericProperty("y");
    entryz = source.GetProperties().GetNumericProperty("z");
    for (int z = 0; z < source.GetNumLayers(); ++z) {
        const Tmx::Layer *layer = source.GetLayer(z);
        for (int y = 0; y < layer->GetHeight(); ++y) {
            for (int x = 0; x < layer->GetWidth(); ++x) {
                int set = layer->GetTileTilesetIndex(x, y);
                if (set < 0 || set >= source.GetNumTilesets()) continue;
                const Tmx::Tile *tile = source.GetTileset(set)->GetTile(layer->GetTileId(x, y));
                if (!tile) continue;
                std::string type = tile->GetProperties().GetLiteralProperty("type");
                if (!type.empty()) addTile(type, x, y, z);
            }
        }
    }
    const Json::Value &items = *ConfigurationProvider::getConfig("config/items.json");
    const Json::Value &creatures = *ConfigurationProvider::getConfig("config/creatures.json");
    for (int group = 0; group < source.GetNumObjectGroups(); ++group) {
        const Tmx::ObjectGroup *objects = source.GetObjectGroup(group);
        for (int index = 0; index < objects->GetNumObjects(); ++index) {
            const Tmx::Object *authored = objects->GetObject(index);
            std::string type = authored->GetType();
            MapObject *object = 0;
            if (items.isMember(type)) object = Item::getItem(type);
            else if (creatures.isMember(type)) object = new Monster(type);
            else {
                int registered = QMetaType::type(type.c_str());
                if (registered != QMetaType::UnknownType)
                    object = static_cast<MapObject *>(QMetaType::create(registered));
            }
            if (!object) {
                qWarning() << "TMX object has no genuine class in this revision:" << type.c_str();
                continue;
            }
            object->setObjectName(QString::fromStdString(authored->GetName()));
            std::map<std::string, std::string> properties = authored->GetProperties().GetList();
            for (auto property : properties)
                object->setProperty(property.first.c_str(), QString::fromStdString(property.second));
            object->moveTo(authored->GetX() / source.GetTileWidth(),
                           authored->GetY() / source.GetTileHeight(), entryz, true);
            addObject(object);
        }
    }
}
