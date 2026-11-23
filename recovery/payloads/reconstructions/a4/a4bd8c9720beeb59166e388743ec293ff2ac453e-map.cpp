#include <locale>
#include <QGraphicsSceneHoverEvent>
#include "map.h"


#include "tile.h"

#include <src/building.h>
#include <src/pathfinder.h>
#include <src/configurationprovider.h>
#include <src/monster.h>
#include <src/player.h>
#include <src/interaction.h>
#include <src/item.h>
#include <src/gamescene.h>
#include <src/gameview.h>
#include <src/scriptmanager.h>

#include <QApplication>
#include <QDesktopWidget>
#include <QGraphicsSceneMouseEvent>
#include <QMetaType>
#include <QMetaProperty>
#include <QWidget>
#include <algorithm>
#include <cstdlib>
#include <vector>
#include <QDebug>
#include <lib/tmx/TmxLayer.h>
#include <lib/tmx/TmxTileset.h>
#include <lib/tmx/TmxTile.h>
#include <lib/tmx/TmxObject.h>
#include <lib/tmx/TmxObjectGroup.h>

namespace {

int tile_size = 50;
const int animation_step_ms = 100;





bool contains_object(std::list<MapObject *> *objects, MapObject *object) {
  return std::find(objects->begin(), objects->end(), object) != objects->end();
}

} // namespace

class ReconstructedPlayerAnimation : public QGraphicsItemAnimation {
public:
    explicit ReconstructedPlayerAnimation(QObject *parent) : QGraphicsItemAnimation(parent) {}
protected:
    void afterAnimationStep(qreal step) override;
};

void ReconstructedPlayerAnimation::afterAnimationStep(qreal) {
    QGraphicsItem *animated = item();
    GameScene *scene = animated ? dynamic_cast<GameScene *>(animated->scene()) : NULL;
    if (scene && scene->getView()) scene->getView()->centerOn(animated);
}

Map::Map(GameScene *scene, std::string file) : scene(scene), entryx(0), entryz(0), entryy(0) {
  connect(CompletionListener::getInstance(), SIGNAL(completed()), this, SLOT(moveCompleted()));
  defaultTiles[0] = "GrassTile";
  engine = new ScriptEngine(this);
  Tmx::Map authored;
  authored.ParseFile(file);
  loadMapFromTmx(authored);
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

  CompletionListener::getInstance()->stop();
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

  CompletionListener::getInstance()->start();
  CompletionListener::getInstance()->run();
}

void Map::moveCompleted() {
  CompletionListener::getInstance()->stop();
  Player *player = scene->getPlayer();
  if (!player) return;
  std::vector<MapObject *> objects;
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

  {
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
    scene->setPlayer((Player *)mapObject);
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
    for (int x = 0; x < width; ++x) for (int y = 0; y < height; ++y)
        addTile("GroundTile", exit.x + x, exit.y + y, exit.z);
    MapObject *entrance = MapObject::createMapObject("Teleporter");
    MapObject *return_gate = MapObject::createMapObject("Teleporter");
    if (!entrance || !return_gate) {
        delete entrance;
        delete return_gate;
        return;
    }
    entrance->name = "generatedEntrance" + std::to_string(enter.x) + "_" + std::to_string(enter.y);
    return_gate->name = "generatedExit" + std::to_string(exit.x) + "_" + std::to_string(exit.y);
    entrance->setProperty("exit", QString::fromStdString(return_gate->name));
    return_gate->setProperty("exit", QString::fromStdString(entrance->name));
    entrance->moveTo(enter.x, enter.y, enter.z, true);
    return_gate->moveTo(exit.x, exit.y, exit.z, true);
    addObject(entrance); addObject(return_gate);
}

void Map::removeObject(MapObject *mapObject) {
  if (!mapObject) {
    return;
  }
  mapObjects.erase(mapObject);
  if (scene->getPlayer()) {
    scene->getPlayer()->getEntered()->remove(mapObject);
  }
  if (mapObject->scene()) {
    mapObject->scene()->removeItem(mapObject);
  }
  // Original Item::onEnter transfers this same object into the player inventory.
  // AnimatedObject registers its lifetime with the genuine Destroyer.
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
      ensureTile(x, y);
    }
  }
}

void Map::ensureTile(int i, int j) {
  if (tiles.find(Coords(i, j, currentMap)) != tiles.end()) {
    return;
  }
  const std::string tile_name = getTile(i, j, currentMap);
  addTile(tile_name.empty() ? "GrassTile" : tile_name, i, j, currentMap);
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





GameScene *Map::getScene() const { return scene; }

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


MapObject::MapObject() : MapObject(0, 0, 0, 0) {}

MapObject::MapObject(int x, int y, int z, int v) {
  posx = x;
  posy = y;
  posz = z;
  setZValue(v);
  setAcceptHoverEvents(true);
  statsView.setParentItem(this);
  statsView.setVisible(true);
  statsView.setText(" ");
  statsView.setPos(-this->mapToParent(0, 0).x(), -statsView.boundingRect().height());
}

void MapObject::moveTo(int x, int y, int z, bool silent) {
    QPointF from = QGraphicsItem::pos();
    posx = x; posy = y; posz = z;
    QPointF to(x * Map::getTileSize(), y * Map::getTileSize());
    if (!silent && map && map->getScene()->getView() && from != to) {
        QGraphicsItemAnimation *animation = inherits("Player")
            ? static_cast<QGraphicsItemAnimation *>(new ReconstructedPlayerAnimation(this))
            : new QGraphicsItemAnimation(this);
        QTimeLine *timeline = new QTimeLine(animation_step_ms, animation);
        animation->setItem(this);
        animation->setTimeLine(timeline);
        animation->setPosAt(0, from); animation->setPosAt(1, to);
        connect(timeline, &QTimeLine::finished, animation, &QObject::deleteLater);
        timeline->start();
    } else { setPos(to); }
    if (map) QGraphicsItem::setVisible(posz == map->getCurrentMap());
    if (!silent) {
        Player *player = map ? map->getScene()->getPlayer() : NULL;
        if (player && player != this && player->getPosX() == posx && player->getPosY() == posy && player->getPosZ() == posz)
            player->addEntered(this);
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

void MapObject::setAnimation(std::string path) {
  AnimatedObject::setAnimation(path, Map::getTileSize());
}

void Map::loadMapFromTmx(Tmx::Map &source) {
    if (source.HasError() || source.GetTileWidth() <= 0 || source.GetTileHeight() <= 0)
        qFatal("TMX reconstruction could not parse the authored map");
    entryx = source.GetProperties().GetNumericProperty("x");
    entryy = source.GetProperties().GetNumericProperty("y");
    entryz = source.GetProperties().GetNumericProperty("z");
    for (int z = 0; z < source.GetNumLayers(); ++z) {
        const Tmx::Layer *layer = source.GetLayer(z);
        boundaries[z] = std::make_pair(layer->GetWidth(), layer->GetHeight());
        for (int y = 0; y < layer->GetHeight(); ++y) for (int x = 0; x < layer->GetWidth(); ++x) {
            int index = layer->GetTileTilesetIndex(x, y);
            if (index < 0 || index >= source.GetNumTilesets()) continue;
            const Tmx::Tile *tile = source.GetTileset(index)->GetTile(layer->GetTileId(x, y));
            if (!tile) continue;
            std::string type = tile->GetProperties().GetLiteralProperty("type");
            if (!type.empty()) addTile(type, x, y, z);
        }
    }
    for (int group = 0; group < source.GetNumObjectGroups(); ++group) {
        const Tmx::ObjectGroup *objects = source.GetObjectGroup(group);
        for (int index = 0; index < objects->GetNumObjects(); ++index) {
            const Tmx::Object *authored = objects->GetObject(index);
            MapObject *object = MapObject::createMapObject(QString::fromStdString(authored->GetType()));
            if (!object) { qWarning() << "TMX object type unavailable in this revision:" << authored->GetType().c_str(); continue; }
            object->name = authored->GetName();
            object->setObjectName(QString::fromStdString(object->name));
            object->loadFromProps(authored->GetProperties());
            object->moveTo(authored->GetX() / source.GetTileWidth(), authored->GetY() / source.GetTileHeight(), entryz, true);
            addObject(object);
        }
    }
}

int Map::getEntryX() { return entryx; }
int Map::getEntryY() { return entryy; }
int Map::getEntryZ() { return entryz; }
std::set<MapObject *> *Map::getObjects() { return &mapObjects; }
MapObject *Map::getObjectByName(std::string name) {
    for (MapObject *object : mapObjects) if (object->name == name) return object;
    return 0;
}
bool Map::removeTile(int x, int y, int z) {
    Coords coords(x, y, z); auto tile = tiles.find(coords);
    if (tile == tiles.end()) return false;
    if (tile->second->scene()) tile->second->scene()->removeItem(tile->second);
    delete tile->second; tiles.erase(tile); erase(coords); return true;
}
MapObject *MapObject::createMapObject(QString qname) {
    std::string name = qname.toStdString();
    Json::Value config = (*ConfigurationProvider::getConfig("config/object.json"))[name];
    std::string class_name = config.get("class", name).asString();
    int registered = QMetaType::type(class_name.c_str());
    if (registered == QMetaType::UnknownType) return 0;
    MapObject *object = static_cast<MapObject *>(QMetaType::create(registered));
    if (object) object->loadFromJson(name);
    return object;
}
void MapObject::loadFromProps(Tmx::PropertySet properties) {
    for (auto property : properties.GetList()) {
        int index = metaObject()->indexOfProperty(property.first.c_str());
        if (index < 0 || !metaObject()->property(index).isUser()) continue;
        QMetaProperty metadata = metaObject()->property(index);
        QVariant value(QString::fromStdString(property.second));
        if (!value.convert(metadata.type()) || !metadata.write(this, value))
            qWarning() << "Could not apply authored TMX property" << property.first.c_str();
    }
}



Coords::Coords()
{
    x=y=z=0;
}

Coords::Coords(int x, int y,int z):x(x),y(y),z(z) {}

bool Coords::operator==(const Coords &other) const
{
    return (x==other.x&&y==other.y&&z==other.z);
}

bool Coords::operator<(const Coords &other) const
{
    if(x<other.x) {
        return true;
    }
    if(y<other.y&&x==other.x) {
        return true;
    }
    if(z<other.z&&x==other.x&&y==other.y) {
        return true;
    }
    return false;
}

std::size_t CoordsHasher::operator()(const Coords &coords) const
{
    using std::size_t;
    int a=(size_t)coords.x;
    int b=(size_t)coords.y;
    int c=(size_t)coords.z;
    return (size_t)(a^b)^(b^c)^(a^c);
}

int Coords::getDist(Coords other) { return std::abs(x-other.x)+std::abs(y-other.y)+std::abs(z-other.z); }

void MapObject::onEnter() {}

void MapObject::onMove() {}

void MapObject::onCreate() {}

void MapObject::onDestroy() {}

std::map<int, std::pair<int, int> > Map::getBounds() { return boundaries; }

int Map::getCurrentXBound() { return boundaries[currentMap].first; }

int Map::getCurrentYBound() { return boundaries[currentMap].second; }

ScriptEngine *Map::getEngine() { return engine; }

namespace {
std::string toLower(const std::string &s) {
  std::string result;
  std::locale loc;
  for (unsigned int i = 0; i < s.length(); ++i) {
    result += std::tolower(s.at(i), loc);
  }
  return result;
}
}

void MapObject::setNumber(int i, int x) {
  this->QGraphicsItem::setVisible(true);
  int px = i % x * Map::getTileSize();
  int py = i / x * Map::getTileSize();
  this->QGraphicsItem::setPos(px, py);
}

bool MapObject::compare(MapObject *item) {
  int value = toLower(typeName).compare(toLower(item->typeName));
  if (value == 0) {
    return this < item;
  }
  return value < 0;
}

void MapObject::hoverEnterEvent(QGraphicsSceneHoverEvent *event) {
  statsView.setVisible(true);
  statsView.setText(tooltip.c_str());
  statsView.setPos(0, 0 - statsView.boundingRect().height());
  event->setAccepted(true);
}

void MapObject::hoverLeaveEvent(QGraphicsSceneHoverEvent *event) {
  statsView.setVisible(false);
  event->setAccepted(true);
}
