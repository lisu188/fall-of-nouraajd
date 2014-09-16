#include "CCreature.h"
#include "CGameScene.h"
#include "CGameView.h"
#include "CLootProvider.h"
#include "CMap.h"
#include "CObjectHandler.h"
#include "CPathFinder.h"
#include "CTile.h"
#include <QDebug>
#include <QJsonArray>
#include <QThreadPool>
#include <algorithm>
#include <cstdlib>

CMap::CMap(CGameScene *scene, QString file)
    : QObject(scene), scene(scene), entryx(0), entryz(0), entryy(0),
      lootProvider(nullptr), handler(nullptr) {
  scene->setMap(this);
  handler = new CObjectHandler(this);
  connect(CompletionListener::getInstance(), SIGNAL(completed()), this,
          SLOT(moveCompleted()));
  loadMap(CConfigurationProvider::getConfig(file).toObject());
}

CMap::~CMap() {
  QThreadPool::globalInstance()->waitForDone();
  std::set<CMapObject *> objects = mapObjects;
  mapObjects.clear();
  for (CMapObject *object : objects) {
    delete object;
  }
  std::set<CTile *> tiles;
  for (auto &entry : *this) {
    tiles.insert(entry.second);
  }
  clear();
  for (CTile *tile : tiles) {
    delete tile;
  }
}

namespace {
int mapInteger(const QJsonValue &value, int fallback = 0) {
  return value.isUndefined() || value.isNull() ? fallback
                                               : value.toVariant().toInt();
}
} // namespace
void CMap::loadMap(const QJsonObject &map) {
  if (!map.contains("layers") || !map.contains("tilesets"))
    qFatal("Expected the historical Tiled JSON map schema");
  QJsonObject properties = map["properties"].toObject();
  entryx = mapInteger(properties["x"]);
  entryy = mapInteger(properties["y"]);
  entryz = mapInteger(properties["z"]);
  QObject::setProperty("recoveryTileWidth", mapInteger(map["tilewidth"], 32));
  QObject::setProperty("recoveryTileHeight", mapInteger(map["tileheight"], 32));
  QJsonObject tiles;
  for (QJsonValue value : map["tilesets"].toArray()) {
    QJsonObject set = value.toObject();
    int first = mapInteger(set["firstgid"], 1);
    QJsonObject definitions = set["tileproperties"].toObject();
    for (auto it = definitions.begin(); it != definitions.end(); ++it)
      tiles[QString::number(first + it.key().toInt())] = it.value();
  }
  QJsonArray layers = map["layers"].toArray();
  for (QJsonValue value : layers) {
    QJsonObject layer = value.toObject();
    if (layer["type"].toString() == "tilelayer")
      handleTileLayer(tiles, layer);
  }
  for (QJsonValue value : layers) {
    QJsonObject layer = value.toObject();
    if (layer["type"].toString() == "objectgroup")
      handleObjectLayer(layer);
  }
  loadingComplete();
}
void CMap::handleTileLayer(const QJsonObject &tileset,
                           const QJsonObject &layer) {
  QJsonObject properties = layer["properties"].toObject();
  int level = mapInteger(properties["level"]);
  int width = layer["width"].toInt();
  int height = layer["height"].toInt();
  QJsonArray data = layer["data"].toArray();
  if (width <= 0 || height <= 0 || data.size() != width * height)
    qFatal("Invalid historical tile-layer dimensions");
  defaultTiles[level] = properties["default"].toString("GrassTile");
  boundaries[level] = std::make_pair(mapInteger(properties["xBound"], width),
                                     mapInteger(properties["yBound"], height));
  for (int y = 0; y < height; ++y)
    for (int x = 0; x < width; ++x) {
      int id = data[x + y * width].toInt();
      if (!id)
        continue;
      QString type = tileset[QString::number(id)].toObject()["type"].toString();
      if (type.isEmpty())
        qFatal("Missing historical tile definition");
      if (!addTile(handler->createMapObject<CTile *>(type), x, y, level))
        qFatal("Cannot add configured tile");
    }
}
void CMap::handleObjectLayer(const QJsonObject &layer) {
  int level = mapInteger(layer["properties"].toObject()["level"]);
  int width = QObject::property("recoveryTileWidth").toInt();
  int height = QObject::property("recoveryTileHeight").toInt();
  if (width <= 0 || height <= 0)
    qFatal("Invalid historical map tile size");
  for (QJsonValue value : layer["objects"].toArray()) {
    QJsonObject definition = value.toObject();
    QString type = definition["type"].toString();
    CMapObject *object = handler->createMapObject<CMapObject *>(type);
    if (!object)
      qFatal("Cannot construct configured map object");
    QString name = definition["name"].toString();
    if (!name.isEmpty())
      object->setObjectName(name);
    QJsonObject properties = definition["properties"].toObject();
    for (auto it = properties.begin(); it != properties.end(); ++it) {
      QJsonValue raw = it.value();
      QVariant property = raw.toVariant();
      if (raw.isString()) {
        QString text = raw.toString();
        bool integer = false;
        int number = text.toInt(&integer);
        property = integer           ? QVariant(number)
                   : text == "true"  ? QVariant(true)
                   : text == "false" ? QVariant(false)
                                     : QVariant(text);
      }
      object->setProperty(it.key(), property);
    }
    addObject(object);
    object->moveTo(mapInteger(definition["x"]) / width,
                   mapInteger(definition["y"]) / height, level);
  }
}

bool CMap::addTile(CTile *tile, int x, int y, int z) {
  if (!tile || contains(x, y, z)) {
    return false;
  }
  tile->posx = x;
  tile->posy = y;
  tile->posz = z;
  tile->setMap(this);
  tile->moveTo(x, y, z);
  tile->setVisible(z == currentMap);
  return true;
}
void CMap::removeTile(int x, int y, int z) {
  auto it = find(Coords(x, y, z));
  if (it == end()) {
    return;
  }
  CTile *tile = it->second;
  erase(it);
  delete tile;
}
bool CMap::contains(int x, int y, int z) {
  return find(Coords(x, y, z)) != end();
}
CTile *CMap::getTile(int x, int y, int z) {
  auto it = find(Coords(x, y, z));
  if (it != end()) {
    return it->second;
  }
  auto bounds = boundaries[z];
  QString type = x < 0 || y < 0 || x >= bounds.first || y >= bounds.second
                     ? "MountainTile"
                     : defaultTiles[z];
  CTile *tile = handler->createMapObject<CTile *>(type);
  if (!tile || !addTile(tile, x, y, z)) {
    qFatal("Cannot construct map tile %s", qPrintable(type));
  }
  return tile;
}
void CMap::ensureTile(int x, int y) { getTile(x, y, currentMap); }
void CMap::ensureSize() {
  CPlayer *player = getPlayer();
  if (!player) {
    return;
  }
  currentMap = player->getPosZ();
  for (int x = -20; x < 20; ++x) {
    for (int y = -10; y < 10; ++y) {
      ensureTile(player->getPosX() + x, player->getPosY() + y);
    }
  }
  for (auto &tile : *this) {
    tile.second->setVisible(tile.first.z == currentMap);
  }
  for (CMapObject *object : mapObjects) {
    object->setVisible(object->getPosZ() == currentMap);
  }
  if (scene->getView()) {
    scene->getView()->centerOn(player);
  }
}
void CMap::addObject(CMapObject *object) {
  if (!object || !mapObjects.insert(object).second) {
    return;
  }
  object->setMap(this);
  CCreature *creature = dynamic_cast<CCreature *>(object);
  if (creature && !creature->getLevel()) {
    creature->levelUp();
    creature->heal(0);
    creature->addMana(0);
  }
  object->onCreate();
}
void CMap::removeObject(CMapObject *object) {
  if (!object || !mapObjects.erase(object)) {
    return;
  }
  object->onDestroy();
  if (object->scene()) {
    object->scene()->removeItem(object);
  }
}
std::set<CMapObject *> *CMap::getObjects() { return &mapObjects; }
CMapObject *CMap::getObjectByName(QString name) {
  for (CMapObject *object : mapObjects) {
    if (object->objectName() == name) {
      return object;
    }
  }
  return nullptr;
}
void CMap::removeObjectByName(QString name) {
  removeObject(getObjectByName(name));
}
QString CMap::addObjectByName(QString name, Coords coords) {
  if (!getTile(coords.x, coords.y, coords.z)->canStep()) {
    return QString();
  }
  CMapObject *object = handler->createMapObject<CMapObject *>(name);
  if (!object) {
    return QString();
  }
  addObject(object);
  object->moveTo(coords.x, coords.y, coords.z);
  return object->objectName();
}
void CMap::replaceTile(QString name, Coords coords) {
  removeTile(coords.x, coords.y, coords.z);
  addTile(handler->createMapObject<CTile *>(name), coords.x, coords.y,
          coords.z);
}
Coords CMap::getLocationByName(QString name) {
  CMapObject *object = getObjectByName(name);
  if (!object) {
    qFatal("Unknown map location %s", qPrintable(name));
  }
  return object->getCoords();
}
CPlayer *CMap::getPlayer() {
  for (CMapObject *object : mapObjects) {
    if (CPlayer *player = dynamic_cast<CPlayer *>(object)) {
      return player;
    }
  }
  return nullptr;
}
CObjectHandler *CMap::getObjectHandler() { return handler; }
CLootProvider *CMap::getLootProvider() {
  if (!lootProvider) {
    lootProvider = new CLootProvider(this);
  }
  return lootProvider;
}

void CMap::move(int x, int y) {
  CPlayer *player = getPlayer();
  if (!player ||
      !getTile(player->getPosX() + x, player->getPosY() + y, player->getPosZ())
           ->canStep()) {
    return;
  }
  CompletionListener::getInstance()->start();
  player->move(x, y);
  std::set<CMapObject *> objects = mapObjects;
  for (CMapObject *object : objects) {
    object->onMove();
  }
  CompletionListener::getInstance()->run();
}
void CMap::moveCompleted() {
  CompletionListener::getInstance()->stop();
  CPlayer *player = getPlayer();
  if (!player) {
    return;
  }
  std::list<CMapObject *> entered;
  std::set<CMapObject *> objects = mapObjects;
  for (CMapObject *object : objects) {
    if (object == player || !(object->getCoords() == player->getCoords())) {
      continue;
    }
    entered.push_back(object);
    if (std::find(player->getEntered()->begin(), player->getEntered()->end(),
                  object) == player->getEntered()->end()) {
      object->onEnter();
    }
  }
  *player->getEntered() = entered;
  getTile(player->getPosX(), player->getPosY(), player->getPosZ())->onStep();
  if (!player->getFightList()->empty()) {
    scene->getView()->showPanel("CFightPanel");
  }
  ensureSize();
  player->updateViews();
}
void CMap::loadingComplete() {
  for (CMapObject *object : mapObjects) {
    object->setVisible(object->getPosZ() == currentMap);
  }
}
void CMap::randomDir(int *direction, int rule) {
  const int offsets[4][2] = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
  int index = rule >= 0 && rule < 4 ? rule : rand() % 4;
  direction[0] = offsets[index][0];
  direction[1] = offsets[index][1];
}

CGameScene *CMap::getScene() const { return scene; }
void CMap::mapUp() { --currentMap; }
void CMap::mapDown() { ++currentMap; }
int CMap::getCurrentMap() { return currentMap; }
int CMap::getEntryX() { return entryx; }
int CMap::getEntryY() { return entryy; }
int CMap::getEntryZ() { return entryz; }
std::map<int, std::pair<int, int>> CMap::getBounds() { return boundaries; }
int CMap::getCurrentXBound() { return boundaries[currentMap].first; }
int CMap::getCurrentYBound() { return boundaries[currentMap].second; }

bool CMap::canStep(int x, int y, int z) { return getTile(x, y, z)->canStep(); }
void CMap::moveTile(CTile *tile, int x, int y, int z) {
  if (!tile)
    return;
  Coords target(x, y, z);
  auto existing = find(target);
  if (existing != end() && existing->second != tile)
    qFatal("Cannot move two owned tiles to the same map coordinate");
  auto old = find(tile->getCoords());
  if (old != end() && old->second == tile)
    erase(old);
  insert(std::make_pair(target, tile));
}
