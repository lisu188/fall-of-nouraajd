#include "map.h"

#include <algorithm>
#include <cstdlib>
#include <vector>
#include <buildings/cave.h>
#include <configuration/configurationprovider.h>
#include <map/tile.h>
#include <view/gamescene.h>

Map::~Map() {
    for (std::map<Coords, Tile *>::iterator it = tiles.begin(); it != tiles.end(); ++it)
        delete (*it).second;
    tiles.clear();
    std::list<MapObject *> objects(mapObjects);
    for (std::list<MapObject *>::iterator it = objects.begin(); it != objects.end(); ++it)
        (*it)->removeFromGame();
    mapObjects.clear();
    clear();
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
    ensureSize(player);
}

std::string Map::getTile(int x, int y) {
    iterator it = find(Coords(x, y));
    if (it != end())
        return (*it).second;
    const std::string name = Tile::getRandomTile();
    addTile(name, x, y);
    return name;
}

bool Map::contains(int x, int y) { return find(Coords(x, y)) != end(); }

bool Map::addTile(std::string name, int x, int y) {
    const Coords coords(x, y);
    if (find(coords) != end())
        return false;
    insert(std::pair<Coords, std::string>(coords, name));
    return true;
}

void Map::addObject(MapObject *object) {
    if (!object)
        return;
    if (std::find(mapObjects.begin(), mapObjects.end(), object) == mapObjects.end())
        mapObjects.push_back(object);
    object->setMap(this);
    getTile(object->getPosX(), object->getPosY());
}

void Map::removeObject(MapObject *object) { mapObjects.remove(object); }

void Map::ensureSize(Player *player) {
    if (!player)
        return;
    const int x = player->getPosX();
    const int y = player->getPosY();
    std::map<Coords, Tile *>::iterator it = tiles.begin();
    while (it != tiles.end()) {
        const Coords coords = (*it).first;
        if (std::abs(coords.first - x) > cacheSize || std::abs(coords.second - y) > cacheSize ||
            (*it).second->className != getTile(coords.first, coords.second)) {
            delete (*it).second;
            tiles.erase(it++);
        } else {
            ++it;
        }
    }
    for (int tx = x - cacheSize; tx <= x + cacheSize; tx++) {
        for (int ty = y - cacheSize; ty <= y + cacheSize; ty++) {
            const Coords coords(tx, ty);
            if (tiles.find(coords) == tiles.end()) {
                Tile *tile = Tile::getTile(getTile(tx, ty), tx, ty);
                tiles.insert(std::pair<Coords, Tile *>(coords, tile));
                tile->addToGame();
            }
        }
    }
}

void Map::addRiver(int length, int x, int y) {
    int dirs[4];
    for (int i = 0; i < length; i++) {
        erase(Coords(x, y));
        addTile("WaterTile", x, y);
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

void Map::addRoad(int length, int x, int y) {
    for (int i = 0; i < length; i++) {
        erase(Coords(x, y));
        addTile("RoadTile", x, y);
        if (rand() % 2 == 0)
            x += rand() % 2 == 0 ? 1 : -1;
        else
            y += rand() % 2 == 0 ? 1 : -1;
    }
}

void Map::addDungeon(int centerx, int centery, int width, int height) {
    for (int x = centerx - width / 2; x <= centerx + width / 2; x++) {
        for (int y = centery - height / 2; y <= centery + height / 2; y++) {
            const bool wall = x == centerx - width / 2 || x == centerx + width / 2 || y == centery - height / 2 ||
                              y == centery + height / 2;
            erase(Coords(x, y));
            addTile(wall ? "MountainTile" : "GroundTile", x, y);
        }
    }
}

void Map::randomDir(int *tab, int rule) {
    for (int i = 0; i < 4; i++)
        tab[i] = i;
    for (int i = 0; i < 4; i++)
        std::swap(tab[i], tab[rand() % std::max(1, std::min(4, rule))]);
}

void Map::loadFromJson(Json::Value config) {
    Json::Value groups = config["tiles"];
    Json::Value::Members names = groups.getMemberNames();
    for (unsigned int n = 0; n < names.size(); n++) {
        Json::Value coords = groups[names[n]];
        for (unsigned int i = 0; i < coords.size(); i++) {
            const int x = coords[i][(unsigned int)0].asInt();
            const int y = coords[i][(unsigned int)1].asInt();
            erase(Coords(x, y));
            addTile(names[n], x, y);
        }
    }
    Json::Value objects = config["objects"];
    names = objects.getMemberNames();
    for (unsigned int n = 0; n < names.size(); n++) {
        Json::Value instances = objects[names[n]];
        for (unsigned int i = 0; i < instances.size(); i++) {
            for (std::list<MapObject *>::iterator it = mapObjects.begin(); it != mapObjects.end(); ++it)
                if ((*it)->className == names[n])
                    (*it)->loadFromJson(instances[i]);
        }
    }
    ensureSize(GameScene::getPlayer());
}

Json::Value Map::saveToJson() {
    Json::Value config;
    for (iterator it = begin(); it != end(); ++it) {
        Json::Value coords(Json::arrayValue);
        coords.append((*it).first.first);
        coords.append((*it).first.second);
        config["tiles"][(*it).second].append(coords);
    }
    for (std::list<MapObject *>::iterator it = mapObjects.begin(); it != mapObjects.end(); ++it)
        if ((*it)->canSave())
            config["objects"][(*it)->className].append((*it)->saveToJson());
    return config;
}

MapObject::MapObject(int x, int y, int z) {
    this->map = 0;
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
        Tile *tile = Tile::getTile(map->getTile(x, y), x, y);
        if (tile) {
            tile->onStep();
            delete tile;
        }
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
    const std::string destination = map->getTile(posx + x, posy + y);
    Json::Value config = (*ConfigurationProvider::getConfig("config/tiles.json"))[destination];
    if (!config.get("canStep", true).asBool())
        return;
    moveTo(posx + x, posy + y);
}

void MapObject::setParentItem(QGraphicsItem *parent) { QGraphicsItem::setParentItem(parent); }

void MapObject::setAnimation(std::string path) { AnimatedObject::setAnimation(path); }

void MapObject::setMap(Map *map) {
    this->map = map;
    if (GameScene::getGame() && scene() != GameScene::getGame())
        GameScene::getGame()->addItem(this);
    setVisible(true);
}

void Map::hide() {
    for (std::map<Coords, Tile *>::iterator it = tiles.begin(); it != tiles.end(); ++it)
        delete (*it).second;
    tiles.clear();
    std::list<MapObject *> objects(mapObjects);
    for (std::list<MapObject *>::iterator it = objects.begin(); it != objects.end(); ++it)
        (*it)->removeFromGame();
    mapObjects = objects;
}

void MapObject::setVisible(bool visible) { QGraphicsItem::setVisible(visible); }

void Map::show() {
    for (std::list<MapObject *>::iterator it = mapObjects.begin(); it != mapObjects.end(); ++it)
        (*it)->setMap(this);
    ensureSize(GameScene::getPlayer());
}
