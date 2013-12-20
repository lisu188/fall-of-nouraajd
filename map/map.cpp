#include "map.h"

#include <algorithm>
#include <cstdlib>
#include <vector>

#include <buildings/cave.h>
#include <map/tile.h>
#include <view/gamescene.h>

// Tiles and map objects are AnimatedObjects owned by the Destroyer, which deletes
// them when the game terminates; the map only drops its references here.
Map::~Map() {
    for (iterator it = begin(); it != end(); ++it)
        (*it).second->removeFromGame();
    std::list<MapObject *> objects(mapObjects);
    for (std::list<MapObject *>::iterator it = objects.begin(); it != objects.end(); ++it)
        (*it)->removeFromGame();
    clear();
    mapObjects.clear();
}

void Map::move(int x, int y) {
    Player *player = GameScene::getPlayer();
    if (!player)
        return;
    player->move(x, y);

    std::vector<MapObject *> objects(mapObjects.begin(), mapObjects.end());
    for (std::vector<MapObject *>::iterator it = objects.begin(); it != objects.end(); ++it) {
        MapObject *object = *it;
        if (object == player || std::find(mapObjects.begin(), mapObjects.end(), object) == mapObjects.end())
            continue;
        if (object->getPosX() != player->getPosX() || object->getPosY() != player->getPosY())
            object->onMove();
        if (std::find(mapObjects.begin(), mapObjects.end(), object) != mapObjects.end() &&
            object->getPosX() == player->getPosX() && object->getPosY() == player->getPosY())
            object->onEnter();
    }
    player->onMove();
}

Tile *Map::getTile(int x, int y) {
    iterator it = find(Coords(x, y));
    if (it != end())
        return (*it).second;
    Tile *tile = Tile::getRandomTile(x, y);
    addTile(tile);
    return tile;
}

bool Map::contains(int x, int y) { return find(Coords(x, y)) != end(); }

void Map::addObject(MapObject *mapObject) {
    if (!mapObject)
        return;
    if (std::find(mapObjects.begin(), mapObjects.end(), mapObject) == mapObjects.end())
        mapObjects.push_back(mapObject);
    getTile(mapObject->getPosX(), mapObject->getPosY());
}

void Map::addRiver(int length, int startx, int starty) {
    int x = startx;
    int y = starty;
    int dirs[4];
    for (int i = 0; i < length; ++i) {
        iterator it = find(Coords(x, y));
        if (it != end())
            erase(it);
        addTile(Tile::getTile("WaterTile", x, y));
        randomDir(dirs, 4);
        switch (dirs[0]) {
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
        iterator it = find(Coords(x, y));
        if (it != end())
            erase(it);
        addTile(Tile::getTile("RoadTile", x, y));
        if (rand() % 2 == 0)
            x += rand() % 2 == 0 ? 1 : -1;
        else
            y += rand() % 2 == 0 ? 1 : -1;
    }
}

void Map::removeObject(MapObject *mapObject) {
    if (mapObject)
        mapObjects.remove(mapObject);
}

void Map::loadFromJson(Json::Value config) {
    // Tiles are saved grouped by tile type, each as its coordinates.
    Json::Value tiles = config["tiles"];
    Json::Value::Members types = tiles.getMemberNames();
    for (unsigned int t = 0; t < types.size(); t++) {
        Json::Value coords = tiles[types[t]];
        for (unsigned int i = 0; i < coords.size(); i++) {
            Tile *tile =
                Tile::getTile(types[t], coords[i][(unsigned int)0].asInt(), coords[i][(unsigned int)1].asInt());
            if (!tile)
                continue;
            iterator it = find(tile->getCoords());
            if (it != end())
                erase(it);
            addTile(tile);
        }
    }
    Json::Value objects = config["objects"];
    Json::Value::Members names = objects.getMemberNames();
    for (unsigned int n = 0; n < names.size(); n++) {
        Json::Value instances = objects[names[n]];
        for (unsigned int i = 0; i < instances.size(); i++) {
            for (std::list<MapObject *>::iterator it = mapObjects.begin(); it != mapObjects.end(); ++it) {
                if ((*it)->className == names[n])
                    (*it)->loadFromJson(instances[i]);
            }
        }
    }
}

Json::Value Map::saveToJson() {
    Json::Value config;
    Json::Value tiles;
    for (iterator it = begin(); it != end(); ++it)
        tiles[(*it).second->className].append((*it).second->saveToJson());
    config["tiles"] = tiles;
    Json::Value objects;
    for (std::list<MapObject *>::iterator it = mapObjects.begin(); it != mapObjects.end(); ++it)
        if ((*it)->canSave())
            objects[(*it)->className].append((*it)->saveToJson());
    config["objects"] = objects;
    return config;
}

void Map::randomDir(int *tab, int rule) {
    for (int i = 0; i < 4; ++i)
        tab[i] = i;
    for (int i = 0; i < 4; ++i)
        std::swap(tab[i], tab[rand() % std::max(1, std::min(4, rule))]);
}

bool Map::addTile(Tile *tile) {
    if (!tile)
        return false;
    if (contains(tile->getCoords().first, tile->getCoords().second))
        return false;
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
    if (GameScene::getGame())
        GameScene::getGame()->addItem(this);
}

MapObject::~MapObject() {
    if (timer)
        delete timer;
    if (animation)
        delete animation;
}

// A silent move only places the object; ordinary moves also step onto the tile.
void MapObject::moveTo(int x, int y, bool silent) {
    posx = x;
    posy = y;
    setPos(x * Tile::size, y * Tile::size);
    if (!silent && map) {
        Tile *tile = map->getTile(x, y);
        if (tile)
            tile->onStep();
    }
}

int MapObject::getPosX() const { return posx; }

int MapObject::getPosY() const { return posy; }

void MapObject::removeFromGame() {
    setVisible(false);
    if (scene())
        scene()->removeItem(this);
    if (map)
        map->removeObject(this);
}

void MapObject::move(int x, int y) {
    if (!map || (x == 0 && y == 0))
        return;
    Tile *destination = map->getTile(posx + x, posy + y);
    if (!destination || !destination->canStep())
        return;
    moveTo(posx + x, posy + y);
}

void MapObject::setParentItem(QGraphicsItem *parent) { QGraphicsItem::setParentItem(parent); }

void MapObject::setAnimation(std::string path) { AnimatedObject::setAnimation(path); }

void clearRange(std::vector<Tile *> *tiles, int start, int stop) {
    if (!tiles)
        return;
    start = std::max(0, start);
    stop = std::min(static_cast<int>(tiles->size()), stop);
    for (int i = start; i < stop; i++)
        (*tiles)[i]->removeFromGame();
}
