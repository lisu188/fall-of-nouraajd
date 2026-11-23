#include <src/lootprovider.h>
#include <locale>
#include <QGraphicsSceneHoverEvent>
#include "CMap.h"


#include "tile.h"

#include <src/CBuilding.h>
#include <src/CPathFinder.h>
#include <src/CConfigurationProvider.h>
#include <src/CCreature.h>
#include <src/CInteraction.h>
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





bool contains_object(std::list<CMapObject *> *objects, CMapObject *object) {
  return std::find(objects->begin(), objects->end(), object) != objects->end();
}

} // namespace
CMap::CMap(CGameScene *scene, std::string file) : scene(scene), entryx(0), entryz(0), entryy(0) {
  connect(CompletionListener::getInstance(), SIGNAL(completed()), this, SLOT(moveCompleted()));
  defaultTiles[0] = "GrassTile";
  engine = new ScriptEngine(this);
  lootProvider = new CLootProvider(this);
  Tmx::Map authored;
  authored.ParseFile(file);
  loadMapFromTmx(authored);
}

CMap::~CMap() {
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

  std::vector<CMapObject *> objects(mapObjects.begin(), mapObjects.end());
  mapObjects.clear();
  for (std::vector<CMapObject *>::iterator it = objects.begin();
       it != objects.end(); ++it) {
    if ((*it)->scene()) {
      (*it)->scene()->removeItem(*it);
    }
    delete *it;
  }
}

bool CMap::addTile(std::string name, int x, int y, int z) {
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
  tile->CMapObject::setMap(this);
  tile->moveTo(x, y, z, true);
  tile->QGraphicsItem::setVisible(z == currentMap);
  tiles.insert(std::pair<Coords, Tile *>(coords, tile));
  insert(std::pair<Coords, std::string>(coords, name));
  return true;
}

int CMap::getTileSize() { return tile_size; }


void CMap::move(int x, int y) {
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
  std::vector<CMapObject *> objects(mapObjects.begin(), mapObjects.end());
  for (std::vector<CMapObject *>::iterator it = objects.begin();
       it != objects.end(); ++it) {
    CMapObject *object = *it;
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
  for (std::vector<CMapObject *>::iterator it = objects.begin();
       it != objects.end(); ++it) {
    CMapObject *object = *it;
    if (!object || object == player ||
        contains_object(player->getEntered(), object)) {
      continue;
    }
    object->onMove();
  }

  CompletionListener::getInstance()->start();
  CompletionListener::getInstance()->run();
}

void CMap::moveCompleted() {
  CompletionListener::getInstance()->stop();
  Player *player = scene->getPlayer();
  if (!player) return;
  std::vector<CMapObject *> objects;
  objects.assign(mapObjects.begin(), mapObjects.end());
  for (std::vector<CMapObject *>::iterator it = objects.begin();
       it != objects.end(); ++it) {
    CMapObject *object = *it;
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
    std::list<CMapObject *> entered(*player->getEntered());
    for (std::list<CMapObject *>::iterator it = entered.begin();
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

std::string CMap::getTile(int x, int y, int z) {
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

bool CMap::contains(int x, int y, int z) {
  return getTile(x, y, z).compare("") != 0;
}

void CMap::addObject(CMapObject *mapObject) {
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

void CMap::randomDir(int *tab, int) {
  tab[0] = 0;
  tab[1] = 1;
  tab[2] = 2;
  tab[3] = 3;
  for (int i = 0; i < 4; ++i) {
    int j = rand() % 4;
    std::swap(tab[i], tab[j]);
  }
}

void CMap::addRiver(int length, int startx, int starty, int startz) {
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

void CMap::addRoad(int length, int startx, int starty, int startz) {
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

void CMap::addDungeon(Coords enter, Coords exit, int width, int height) {
    for (int x = 0; x < width; ++x) for (int y = 0; y < height; ++y)
        addTile("GroundTile", exit.x + x, exit.y + y, exit.z);
    CMapObject *entrance = createMapObject<CMapObject *>(std::string("Teleporter"));
    CMapObject *return_gate = createMapObject<CMapObject *>(std::string("Teleporter"));
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

void CMap::removeObject(CMapObject *mapObject) {
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
  // CAnimatedObject registers its lifetime with the genuine Destroyer.
}









void CMap::ensureSize() {
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

void CMap::ensureTile(int i, int j) {
  if (tiles.find(Coords(i, j, currentMap)) != tiles.end()) {
    return;
  }
  const std::string tile_name = getTile(i, j, currentMap);
  addTile(tile_name.empty() ? "GrassTile" : tile_name, i, j, currentMap);
}

void CMap::hide() {
  for (std::unordered_map<Coords, Tile *, CoordsHasher>::iterator it = tiles.begin(); it != tiles.end();
       ++it) {
    if ((*it).second) {
      (*it).second->QGraphicsItem::setVisible(false);
    }
  }
  for (std::set<CMapObject *>::iterator it = mapObjects.begin();
       it != mapObjects.end(); ++it) {
    if (*it) {
      (*it)->QGraphicsItem::setVisible(false);
    }
  }
}





CGameScene *CMap::getScene() const { return scene; }

void CMap::showAll() {
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

  for (std::set<CMapObject *>::iterator it = mapObjects.begin();
       it != mapObjects.end(); ++it) {
    CMapObject *object = *it;
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

void CMap::mapUp() { ++currentMap; }

void CMap::mapDown() { --currentMap; }

int CMap::getCurrentMap() { return currentMap; }


void CMap::loadMapFromTmx(Tmx::Map &source) {
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
            CMapObject *object = createMapObject<CMapObject *>(authored->GetType());
            if (!object) { qWarning() << "TMX object type unavailable in this revision:" << authored->GetType().c_str(); continue; }
            object->name = authored->GetName();
            object->setObjectName(QString::fromStdString(object->name));
            object->loadFromProps(authored->GetProperties());
            object->moveTo(authored->GetX() / source.GetTileWidth(), authored->GetY() / source.GetTileHeight(), entryz, true);
            addObject(object);
        }
    }
}

int CMap::getEntryX() { return entryx; }
int CMap::getEntryY() { return entryy; }
int CMap::getEntryZ() { return entryz; }
std::set<CMapObject *> *CMap::getObjects() { return &mapObjects; }
CMapObject *CMap::getObjectByName(std::string name) {
    for (CMapObject *object : mapObjects) if (object->name == name) return object;
    return 0;
}
bool CMap::removeTile(int x, int y, int z) {
    Coords coords(x, y, z); auto tile = tiles.find(coords);
    if (tile == tiles.end()) return false;
    if (tile->second->scene()) tile->second->scene()->removeItem(tile->second);
    delete tile->second; tiles.erase(tile); erase(coords); return true;
}
std::map<int, std::pair<int, int> > CMap::getBounds() { return boundaries; }

int CMap::getCurrentXBound() { return boundaries[currentMap].first; }

int CMap::getCurrentYBound() { return boundaries[currentMap].second; }

ScriptEngine *CMap::getEngine() { return engine; }
CLootProvider *CMap::getLootProvider() { return lootProvider; }

bool CMap::removeObjectByName(std::string name) {
    CMapObject *object = getObjectByName(name);
    if (!object) return false;
    removeObject(object);
    return true;
}
std::string CMap::addObjectByName(std::string name, Coords coords) {
    CMapObject *object = createMapObject<CMapObject *>(name);
    if (!object) return "";
    object->moveTo(coords.x, coords.y, coords.z, true);
    addObject(object);
    return object->name;
}
void CMap::replaceTile(std::string name, Coords coords) {
    removeTile(coords.x, coords.y, coords.z);
    addTile(name, coords.x, coords.y, coords.z);
}
Coords CMap::getLocationByName(std::string name) {
    CMapObject *object = getObjectByName(name);
    return object ? object->getCoords() : Coords();
}
Player *CMap::getPlayer() { return scene->getPlayer(); }
