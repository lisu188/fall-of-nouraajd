#include "CCreature.h"
#include "CGameScene.h"
#include "CGameView.h"
#include "CLootProvider.h"
#include "CMap.h"
#include "CObjectHandler.h"
#include "CPathFinder.h"
#include "CTile.h"
#include <QDebug>
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
  Tmx::Map loaded;
  loaded.ParseFile(file.toStdString());
  if (loaded.HasError()) {
    qFatal("Cannot load TMX map: %s", loaded.GetErrorText().c_str());
  }
  loadMapFromTmx(loaded);
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

void CMap::loadMapFromTmx(Tmx::Map &loaded) {
  const Tmx::PropertySet &properties = loaded.GetProperties();
  entryx = properties.GetNumericProperty("x");
  entryy = properties.GetNumericProperty("y");
  entryz = properties.GetNumericProperty("z");
  for (const Tmx::Layer *layer : loaded.GetLayers()) {
    const Tmx::PropertySet &layer_properties = layer->GetProperties();
    int level = layer_properties.GetNumericProperty("level");
    QString default_tile =
        layer_properties.HasProperty("default")
            ? QString::fromStdString(
                  layer_properties.GetLiteralProperty("default"))
            : QString();
    defaultTiles[level] = default_tile.isEmpty() ? "GrassTile" : default_tile;
    boundaries[level] =
        std::make_pair(layer_properties.HasProperty("xBound")
                           ? layer_properties.GetNumericProperty("xBound")
                           : layer->GetWidth(),
                       layer_properties.HasProperty("yBound")
                           ? layer_properties.GetNumericProperty("yBound")
                           : layer->GetHeight());
    for (int y = 0; y < layer->GetHeight(); ++y) {
      for (int x = 0; x < layer->GetWidth(); ++x) {
        int set = layer->GetTileTilesetIndex(x, y);
        if (set < 0) {
          continue;
        }
        const Tmx::Tile *definition =
            loaded.GetTileset(set)->GetTile(layer->GetTileId(x, y));
        if (!definition) {
          continue;
        }
        const Tmx::PropertySet &tile_properties = definition->GetProperties();
        QString type = tile_properties.HasProperty("type")
                           ? QString::fromStdString(
                                 tile_properties.GetLiteralProperty("type"))
                           : QString();
        if (!type.isEmpty()) {
          addTile(handler->createMapObject<CTile *>(type), x, y, level);
        }
      }
    }
  }
  for (const Tmx::ObjectGroup *group : loaded.GetObjectGroups()) {
    int level = group->GetProperties().GetNumericProperty("level");
    for (const Tmx::Object *definition : group->GetObjects()) {
      QString type = QString::fromStdString(definition->GetType());
      CMapObject *object = handler->createMapObject<CMapObject *>(type);
      if (!object) {
        qFatal("Cannot construct authored map object %s", qPrintable(type));
      }
      if (!definition->GetName().empty()) {
        object->setObjectName(QString::fromStdString(definition->GetName()));
      }
      object->loadFromProps(definition->GetProperties());
      addObject(object);
      object->moveTo(definition->GetX() / loaded.GetTileWidth(),
                     definition->GetY() / loaded.GetTileHeight(), level, true);
    }
  }
  loadingComplete();
}

bool CMap::addTile(CTile *tile, int x, int y, int z) {
  if (!tile || contains(x, y, z)) {
    return false;
  }
  tile->posx = x;
  tile->posy = y;
  tile->posz = z;
  tile->setMap(this);
  tile->moveTo(x, y, z, true);
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
  object->moveTo(coords.x, coords.y, coords.z, true);
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
    scene->getView()->showFightView();
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
void CMap::addRiver(int length, int x, int y, int z) {
  for (int i = 0; i < length; ++i) {
    replaceTile("WaterTile", Coords(x, y, z));
    int direction[2];
    randomDir(direction, -1);
    x += direction[0];
    y += direction[1];
  }
}
void CMap::addRoad(int length, int x, int y, int z) {
  for (int i = 0; i < length; ++i) {
    replaceTile("RoadTile", Coords(x, y, z));
    int direction[2];
    randomDir(direction, -1);
    x += direction[0];
    y += direction[1];
  }
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
