#include "CCreature.h"
#include "CGuiHandler.h"
#include "CGameScene.h"
#include "CGameView.h"
#include "CLootProvider.h"
#include "CMap.h"
#include "CGamePanel.h"
#include "CGuiHandler.h"
#include "CObjectHandler.h"
#include "CPathFinder.h"
#include "CTile.h"
#include <QDebug>
#include <QJsonArray>
#include <QFile>
#include "CScriptEngine.h"
#include "CResourcesHandler.h"
#include <QThreadPool>
#include <algorithm>
#include <cstdlib>

CMap::CMap(CGameScene *scene, QString mapPath)
    : QObject(scene), scene(scene), entryx(0), entryz(0), entryy(0),
      lootProvider(nullptr), handler(nullptr), mapPath(mapPath) {
  handler = new CObjectHandler(this);
  guiHandler = new CGuiHandler(this);
  eventHandler = new CEventHandler(this);
  loadMap(mapPath);
}

CMap::~CMap() {
  QThreadPool::globalInstance()->waitForDone();
  std::set<CMapObject *> objects;
  for (const auto &entry : mapObjects) objects.insert(entry.second);
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
void CMap::loadMap(QString mapPath) {
  auto finishLoading = [this]() {
    for (const auto &entry : mapObjects) {
      auto *object = entry.second;
      object->setVisible(object->getPosZ() == currentLevel);
    }
  };
  namespace py = boost::python;
  auto *engine = CScriptEngine::getInstance();
  py::object mapLoader = py::import("_core").attr("CMapScriptLoader")(py::ptr(this));
  py::extract<CMapScriptLoader *>(mapLoader)()->setParent(nullptr);
  py::object finders = py::import("sys").attr("meta_path");
  finders.attr("append")(mapLoader);
  try {
    engine->executeScript("import " + getMapName());
  } catch (...) {
    finders.attr("remove")(mapLoader);
    throw;
  }
  finders.attr("remove")(mapLoader);
  lootProvider = new CLootProvider(this);
  const auto map = CConfigurationProvider::getConfig(mapPath + "/map.json").toObject();
  if (map["map"].isObject() && map["state"].isObject()) {
    const QJsonObject terrain = map["map"].toObject();
    const QJsonObject defaults = terrain["default"].toObject();
    for (auto it = defaults.begin(); it != defaults.end(); ++it)
      defaultTiles[it.key().toInt()] = it.value().toString();
    for (auto it = terrain.begin(); it != terrain.end(); ++it) {
      if (it.key() == "default") continue;
      for (const QJsonValue &tile : it.value().toArray()) {
        const QJsonArray coords = tile.toArray();
        if (coords.size() != 3) qFatal("Invalid historical map coordinate");
        if (!addTile(handler->createMapObject<CTile *>(it.key()),
                     mapInteger(coords[0]), mapInteger(coords[1]), mapInteger(coords[2])))
          qFatal("Cannot add authored sparse map tile");
      }
    }
    const QJsonObject state = map["state"].toObject();
    for (auto group = state.begin(); group != state.end(); ++group) {
      const QJsonObject types = group.value().toObject();
      for (auto type = types.begin(); type != types.end(); ++type) {
        for (const QJsonValue &record : type.value().toArray()) {
          auto *object = handler->createMapObject<CMapObject *>(type.key());
          if (!object) qFatal("Cannot create authored sparse map object");
          addObject(object);
          if (record.isArray()) {
            const auto coords = record.toArray();
            if (coords.size() != 3) qFatal("Invalid historical object coordinate");
            object->moveTo(mapInteger(coords[0]), mapInteger(coords[1]), mapInteger(coords[2]));
            continue;
          }
          const auto properties = record.toObject();
          const auto coords = properties["coords"].toObject();
          if (auto *creature = dynamic_cast<CCreature *>(object)) {
            const auto stats = properties["initStats"].toObject();
            for (auto stat = stats.begin(); stat != stats.end(); ++stat)
              creature->getStats()->setProperty(stat.key(), stat.value().toVariant());
            creature->attribChange();
            creature->setExp(mapInteger(properties["exp"], creature->getExp()));
            creature->setHp(mapInteger(properties["hp"], creature->getHp()));
            creature->setMana(mapInteger(properties["mana"], creature->getMana()));
            creature->setGold(mapInteger(properties["gold"], creature->getGold()));
          }
          object->moveTo(mapInteger(coords["x"]), mapInteger(coords["y"]), mapInteger(coords["z"]));
        }
      }
    }
    finishLoading();
    return;
  }
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
  finishLoading();
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
  tile->setVisible(z == currentLevel);
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
void CMap::ensureTile(int x, int y) { getTile(x, y, currentLevel); }
void CMap::ensureSize() {
  CPlayer *player = getPlayer();
  if (!player) {
    return;
  }
  currentLevel = player->getPosZ();
  for (int x = -20; x < 20; ++x) {
    for (int y = -10; y < 10; ++y) {
      ensureTile(player->getPosX() + x, player->getPosY() + y);
    }
  }
  for (auto &tile : *this) {
    tile.second->setVisible(tile.first.z == currentLevel);
  }
  for (const auto &entry : mapObjects) {
    auto *object = entry.second;
    object->setVisible(object->getPosZ() == currentLevel);
  }
  if (scene->getView()) {
    scene->getView()->centerOn(player);
  }
}
void CMap::addObject(CMapObject *object) {
  if (!object || !mapObjects.emplace(object->objectName(), object).second) {
    return;
  }
  object->setMap(this);
  CCreature *creature = dynamic_cast<CCreature *>(object);
  if (creature && !creature->getLevel()) {
    creature->levelUp();
    creature->heal(0);
    creature->addMana(0);
  }
  eventHandler->gameEvent(new CGameEvent(CGameEvent::onCreate), object);
}
void CMap::removeObject(CMapObject *object) {
  if (!object || !mapObjects.erase(object->objectName())) {
    return;
  }
  eventHandler->gameEvent(new CGameEvent(CGameEvent::onDestroy), object);
  scene->removeObject(object);
}
CMapObject *CMap::getObjectByName(QString name) {
  for (const auto &entry : mapObjects) {
    auto *object = entry.second;
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
  for (const auto &entry : mapObjects) {
    auto *object = entry.second;
    if (CPlayer *player = dynamic_cast<CPlayer *>(object)) {
      return player;
    }
  }
  return nullptr;
}
const CObjectHandler *CMap::getObjectHandler() const { return handler; }
const CLootProvider *CMap::getLootProvider() const {
  return lootProvider;
}

const CEventHandler *CMap::getEventHandler() const { return eventHandler; }

void CMap::applyEffects() {
  for (auto *object : getMapObjectsClone()) {
    if (auto *creature = dynamic_cast<CCreature *>(object)) creature->applyEffects();
  }
}

void CMap::resolveFights() {
  auto *player = getPlayer();
  if (player && !player->getFightList()->empty()) {
    if (auto *panel = getGuiHandler()->getPanel("CFightPanel")) panel->showPanel();
  }
}

void CMap::move() {
  auto *player = getPlayer();
  if (!player) return;
  const auto objects = getMapObjectsClone();
  for (auto *object : objects) {
    if (getObjectByName(object->objectName()) != object) continue;
    if (auto *moveable = dynamic_cast<Moveable *>(object)) {
      auto step = moveable->getNextMove();
      if (step.x || step.y || step.z) object->move(step);
    }
  }
  for (auto *object : objects) {
    if (getObjectByName(object->objectName()) == object)
      eventHandler->gameEvent(new CGameEvent(CGameEvent::onMove, player), object);
  }
  for (auto *object : objects) {
    auto *visitor = dynamic_cast<CCreature *>(object);
    if (!visitor || getObjectByName(visitor->objectName()) != visitor) continue;
    QStringList prior = visitor->QObject::property("recoveredEnterContacts").toStringList();
    QStringList current;
    for (auto *target : objects) {
      if (target == visitor || !dynamic_cast<Visitable *>(target) ||
          getObjectByName(target->objectName()) != target) continue;
      QString name = target->objectName();
      if (target->getCoords() == visitor->getCoords()) {
        current.push_back(name);
        if (!prior.contains(name))
          eventHandler->gameEvent(new CGameEvent(CGameEvent::onEnter, visitor), target);
      } else if (prior.contains(name)) {
        eventHandler->gameEvent(new CGameEvent(CGameEvent::onLeave, visitor), target);
      }
      if (getObjectByName(visitor->objectName()) != visitor) break;
    }
    visitor->QObject::setProperty("recoveredEnterContacts", current);
  }
  resolveFights();
  ensureSize();
  player->updateViews();
  Q_EMIT nextMove();
}

std::set<CMapObject *> CMap::getMapObjectsClone() {
  return getIf([](CMapObject *) { return true; });
}

CGameScene *CMap::getScene() const { return scene; }
void CMap::mapUp() { --currentLevel; }
void CMap::mapDown() { ++currentLevel; }
int CMap::getCurrentMap() { return currentLevel; }
int CMap::getEntryX() { return entryx; }
int CMap::getEntryY() { return entryy; }
int CMap::getEntryZ() { return entryz; }
std::map<int, std::pair<int, int>> CMap::getBounds() { return boundaries; }
int CMap::getCurrentXBound() { return boundaries[currentLevel].first; }
int CMap::getCurrentYBound() { return boundaries[currentLevel].second; }

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

CGuiHandler *CMap::getGuiHandler() const { return guiHandler; }

QString CMap::getMapPath() const { return mapPath; }
QString CMap::getMapName() { return mapPath.section("/", -1); }

bool CMap::canStep(Coords &coords) { return canStep(coords.x, coords.y, coords.z); }
