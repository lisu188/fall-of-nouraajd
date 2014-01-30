#include "map.h"

#include <QGraphicsSceneMouseEvent>
#include <algorithm>
#include <buildings/cave.h>
#include <buildings/dungeon.h>
#include <buildings/teleporter.h>
#include <configuration/configurationprovider.h>
#include <creatures/monster.h>
#include <creatures/player.h>
#include <cstdlib>
#include <interactions/interaction.h>
#include <items/armor.h>
#include <items/potion.h>
#include <items/weapon.h>
#include <map/tile.h>
#include <sstream>
#include <vector>
#include <view/gamescene.h>

namespace {
bool itemGroup(const std::string &type) {
    return type == "Item" || type == "Weapon" || type == "Armor" || type == "Potion" || type == "SmallWeapon" ||
           type == "Helmet" || type == "Belt" || type == "Boots" || type == "Gloves" || type == "Shield" ||
           type == "Pants";
}
struct MapJsonState {
    Json::Value unimplementedObjects;
};
std::map<Map *, MapJsonState> mapJsonStates;
Dungeon *configuredDungeon(const Coords &entry, const Coords &exit) {
    Json::Value state(Json::arrayValue);
    state.append(entry.x);
    state.append(entry.y);
    state.append(entry.z);
    state.append(exit.x);
    state.append(exit.y);
    state.append(exit.z);
    Dungeon *dungeon = new Dungeon();
    dungeon->loadFromJson(state);
    return dungeon;
}

} // namespace

Map::Map(QGraphicsScene *scene) : scene(scene) {}

Map::~Map() {
    mapJsonStates.erase(this);
    for (std::map<Coords, Tile *>::iterator it = tiles.begin(); it != tiles.end(); ++it)
        delete (*it).second;
    tiles.clear();
    std::set<MapObject *> objects(mapObjects);
    for (std::set<MapObject *>::iterator it = objects.begin(); it != objects.end(); ++it)
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
        if (object == player || mapObjects.find(object) == mapObjects.end())
            continue;
        if (object->getPosZ() == player->getPosZ() &&
            (object->getPosX() != player->getPosX() || object->getPosY() != player->getPosY()))
            object->onMove();
        if (mapObjects.find(object) != mapObjects.end() && object->getPosZ() == player->getPosZ() &&
            object->getPosX() == player->getPosX() && object->getPosY() == player->getPosY())
            object->onEnter();
    }
    player->onMove();
    ensureSize(player);
}

std::string Map::getTile(int x, int y, int z) {
    iterator it = find(Coords(x, y, z));
    if (it != end())
        return (*it).second;
    std::map<int, std::string>::iterator fallback = defaultTiles.find(z);
    const std::string name = fallback == defaultTiles.end() ? "GrassTile" : fallback->second;
    addTile(name, x, y, z);
    return name;
}

bool Map::contains(int x, int y, int z) { return find(Coords(x, y, z)) != end(); }

bool Map::addTile(std::string name, int x, int y, int z) {
    const Coords coords(x, y, z);
    if (find(coords) != end())
        return false;
    insert(std::pair<Coords, std::string>(coords, name));
    return true;
}

void Map::addObject(MapObject *object) {
    if (!object)
        return;
    mapObjects.insert(object);
    object->setMap(this);
    getTile(object->getPosX(), object->getPosY(), object->getPosZ());
}

void Map::removeObject(MapObject *object) {
    if (!object)
        return;
    mapObjects.erase(object);
    if (object->scene() == scene)
        scene->removeItem(object);
    if (object->getMap() == this)
        object->setMap(0);
}

void Map::ensureSize(Player *player) {
    if (!player)
        return;
    const int cacheSize = 25;
    const int x = player->getPosX();
    const int y = player->getPosY();
    const int z = player->getPosZ();
    currentMap = z;
    for (std::set<MapObject *>::iterator object = mapObjects.begin(); object != mapObjects.end(); ++object)
        (*object)->setVisible((*object)->getPosZ() == currentMap);
    std::map<Coords, Tile *>::iterator it = tiles.begin();
    while (it != tiles.end()) {
        const Coords coords = (*it).first;
        if (coords.z != z || std::abs(coords.x - x) > cacheSize || std::abs(coords.y - y) > cacheSize ||
            (*it).second->className != getTile(coords.x, coords.y, coords.z)) {
            delete (*it).second;
            tiles.erase(it++);
        } else {
            ++it;
        }
    }
    for (int tx = x - cacheSize; tx <= x + cacheSize; tx++) {
        for (int ty = y - cacheSize; ty <= y + cacheSize; ty++) {
            const Coords coords(tx, ty, z);
            if (tiles.find(coords) == tiles.end()) {
                Tile *tile = Tile::getTile(getTile(tx, ty, z), tx, ty, z);
                tiles.insert(std::pair<Coords, Tile *>(coords, tile));
                tile->addToScene(scene);
            }
        }
    }
}

void Map::addRiver(int length, int x, int y, int z) {
    int dirs[4];
    for (int i = 0; i < length; i++) {
        erase(Coords(x, y, z));
        addTile("WaterTile", x, y, z);
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

void Map::addRoad(int length, int x, int y, int z) {
    for (int i = 0; i < length; i++) {
        erase(Coords(x, y, z));
        addTile("RoadTile", x, y, z);
        if (rand() % 2 == 0)
            x += rand() % 2 == 0 ? 1 : -1;
        else
            y += rand() % 2 == 0 ? 1 : -1;
    }
}

void Map::addDungeon(Coords enter, Coords exit, int width, int height) {
    const int centerx = exit.x;
    const int centery = exit.y;
    const int centerz = exit.z;
    for (int x = centerx - width / 2; x <= centerx + width / 2; x++) {
        for (int y = centery - height / 2; y <= centery + height / 2; y++) {
            const bool wall = x == centerx - width / 2 || x == centerx + width / 2 || y == centery - height / 2 ||
                              y == centery + height / 2;
            erase(Coords(x, y, centerz));
            addTile(wall ? "MountainTile" : "GroundTile", x, y, centerz);
        }
    }
    addObject(configuredDungeon(enter, exit));
    addObject(configuredDungeon(exit, enter));
}

void Map::randomDir(int *tab, int rule) {
    for (int i = 0; i < 4; i++)
        tab[i] = i;
    for (int i = 0; i < 4; i++)
        std::swap(tab[i], tab[rand() % std::max(1, std::min(4, rule))]);
}

void Map::loadMapFromJson(Json::Value config) {
    Json::Value groups = config.isMember("tiles") ? config["tiles"] : config;
    if (!groups.isObject())
        return;
    defaultTiles.clear();
    Json::Value defaults = groups["default"];
    Json::Value::Members depths = defaults.getMemberNames();
    for (unsigned int i = 0; i < depths.size(); ++i)
        defaultTiles[std::atoi(depths[i].c_str())] = defaults[depths[i]].asString();
    Json::Value::Members names = groups.getMemberNames();
    for (unsigned int n = 0; n < names.size(); n++) {
        Json::Value coords = groups[names[n]];
        if (!coords.isArray())
            continue;
        for (unsigned int i = 0; i < coords.size(); i++) {
            if (!coords[i].isArray() || coords[i].size() < 2)
                continue;
            const int x = coords[i][(unsigned int)0].asInt();
            const int y = coords[i][(unsigned int)1].asInt();
            const int z = coords[i].size() > 2 ? coords[i][(unsigned int)2].asInt() : 0;
            erase(Coords(x, y, z));
            addTile(names[n], x, y, z);
        }
    }
    ensureSize(GameScene::getPlayer());
}

Json::Value Map::saveMapToJson() {
    Json::Value config(Json::objectValue);
    for (std::map<int, std::string>::iterator it = defaultTiles.begin(); it != defaultTiles.end(); ++it) {
        std::ostringstream depth;
        depth << it->first;
        config["default"][depth.str()] = it->second;
    }
    for (iterator it = begin(); it != end(); ++it) {
        Json::Value coords(Json::arrayValue);
        coords.append((*it).first.x);
        coords.append((*it).first.y);
        coords.append((*it).first.z);
        config[(*it).second].append(coords);
    }
    return config;
}

void Map::loadStateFromJson(Json::Value config) {
    if (!config.isObject())
        return;
    if (config.isMember("objects")) {
        Json::Value objects = config["objects"];
        Json::Value::Members names = objects.getMemberNames();
        for (unsigned int n = 0; n < names.size(); n++) {
            Json::Value instances = objects[names[n]];
            for (unsigned int i = 0; i < instances.size(); i++) {
                for (std::set<MapObject *>::iterator it = mapObjects.begin(); it != mapObjects.end(); ++it)
                    if ((*it)->className == names[n])
                        (*it)->loadFromJson(instances[i]);
            }
        }
    } else {
        Json::Value::Members classes = config.getMemberNames();
        for (unsigned int c = 0; c < classes.size(); c++) {
            const std::string type = classes[c];
            if (type != "Cave" && type != "Dungeon" && type != "Teleporter" && type != "Monster" && type != "Player" &&
                !itemGroup(type) && type != "Interaction") {
                // Preserve classes whose historical construction API remains
                // unavailable.
                mapJsonStates[this].unimplementedObjects[type] = config[type];
                continue;
            }
            Json::Value::Members names = config[type].getMemberNames();
            for (unsigned int n = 0; n < names.size(); n++) {
                Json::Value instances = config[type][names[n]];
                for (unsigned int i = 0; i < instances.size(); i++) {
                    Json::Value state = instances[i];
                    MapObject *object = 0;
                    if (type == "Cave" && state.isArray() && state.size() >= 3) {
                        Cave *cave = new Cave();
                        cave->loadFromJson(state);
                        object = cave;
                    } else if (type == "Teleporter" && state.isArray() && state.size() >= 3) {
                        Teleporter *teleporter = new Teleporter();
                        teleporter->loadFromJson(state);
                        object = teleporter;
                    } else if (type == "Dungeon" && state.isArray() && state.size() >= 6) {
                        Dungeon *dungeon = new Dungeon();
                        dungeon->loadFromJson(state);
                        object = dungeon;
                    } else if (type == "Monster" && state.isObject()) {
                        object = new Monster(names[n], state);
                    } else if (type == "Player" && state.isObject() && !GameScene::getPlayer()) {
                        Player *player = new Player(names[n], state);
                        GameScene::setPlayer(player);
                        object = player;
                    }
                    if (itemGroup(type) && state.isArray() && state.size() >= 3) {
                        object = Item::getItem(names[n].c_str());
                        if (object)
                            object->moveTo(state[(unsigned int)0].asInt(), state[(unsigned int)1].asInt(),
                                           state[(unsigned int)2].asInt(), true);
                    } else if (type == "Interaction" && state.isArray() && state.size() >= 3) {
                        object = Interaction::getInteraction(names[n]);
                        if (object)
                            object->loadFromJson(state);
                    }
                    if (object)
                        addObject(object);
                    else if (itemGroup(type))
                        mapJsonStates[this].unimplementedObjects[type][names[n]].append(state);
                }
            }
        }
    }
    ensureSize(GameScene::getPlayer());
}

Json::Value Map::saveStateToJson() {
    Json::Value config = mapJsonStates[this].unimplementedObjects;
    for (std::set<MapObject *>::iterator it = mapObjects.begin(); it != mapObjects.end(); ++it) {
        MapObject *object = *it;
        if (!object->canSave())
            continue;
        std::string type;
        if (dynamic_cast<Player *>(object))
            type = "Player";
        else if (dynamic_cast<Monster *>(object))
            type = "Monster";
        else if (dynamic_cast<Cave *>(object))
            type = "Cave";
        else if (dynamic_cast<Dungeon *>(object))
            type = "Dungeon";
        else if (dynamic_cast<Teleporter *>(object))
            type = "Teleporter";
        else if (dynamic_cast<Potion *>(object))
            type = "Potion";
        else if (dynamic_cast<Armor *>(object))
            type = "Armor";
        else if (dynamic_cast<Weapon *>(object))
            type = "Weapon";
        else if (dynamic_cast<Item *>(object))
            type = object->metaObject()->className();
        else if (dynamic_cast<Interaction *>(object))
            type = "Interaction";
        if (!type.empty())
            config[type][object->className].append(object->saveToJson());
    }
    return config;
}

void Map::loadFromJson(Json::Value config) {
    if (!config.isObject())
        return;
    loadMapFromJson(config["map"]);
    loadStateFromJson(config["state"]);
}

Json::Value Map::saveToJson() {
    Json::Value config;
    config["map"] = saveMapToJson();
    config["state"] = saveStateToJson();
    return config;
}

MapObject::MapObject() : MapObject(0, 0, 0, 0) {}

MapObject::MapObject(int x, int y, int z, int v) {
    this->map = 0;
    posx = x;
    posy = y;
    posz = z;
    animation = 0;
    timer = 0;
    setZValue(v);
    statsView.setParentItem(this);
    statsView.setVisible(false);
    setPos(x * (map ? map->getTileSize() : 50), y * (map ? map->getTileSize() : 50));
}

MapObject::~MapObject() {
    if (timer)
        delete timer;
    if (animation)
        delete animation;
}

// A silent move only places the object; ordinary moves also step onto the tile.
void MapObject::moveTo(int x, int y, int z, bool silent) {
    posx = x;
    posy = y;
    posz = z;
    setPos(x * (map ? map->getTileSize() : 50), y * (map ? map->getTileSize() : 50));
    if (!silent && map) {
        Tile *tile = Tile::getTile(map->getTile(x, y, z), x, y, z);
        if (tile) {
            tile->onStep();
            delete tile;
        }
    }
}

int MapObject::getPosX() const { return posx; }

int MapObject::getPosY() const { return posy; }

int MapObject::getPosZ() const { return posz; }

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
    const std::string destination = map->getTile(posx + x, posy + y, posz);
    Json::Value config = (*ConfigurationProvider::getConfig("config/tiles.json"))[destination];
    if (!config.get("canStep", true).asBool())
        return;
    moveTo(posx + x, posy + y, posz);
}

void MapObject::setAnimation(std::string path) { AnimatedObject::setAnimation(path, Map::getTileSize()); }

void MapObject::setMap(Map *map) {
    this->map = map;
    if (map && map->getScene() && scene() != map->getScene())
        map->getScene()->addItem(this);
    MapObject::moveTo(posx, posy, posz, true);
    setVisible(true);
}

void Map::hide() {
    for (std::map<Coords, Tile *>::iterator it = tiles.begin(); it != tiles.end(); ++it)
        delete (*it).second;
    tiles.clear();
    std::set<MapObject *> objects(mapObjects);
    for (std::set<MapObject *>::iterator it = objects.begin(); it != objects.end(); ++it)
        (*it)->removeFromGame();
    mapObjects = objects;
}

void MapObject::setVisible(bool visible) { QGraphicsItem::setVisible(visible); }

QGraphicsScene *Map::getScene() const { return scene; }

int Map::getTileSize() {
    Json::Value *config = ConfigurationProvider::getConfig("config/init.json");
    const bool editor = config->get("editor", false).asBool();
    const int size = config->get(editor ? "mapSize" : "gameSize", 50).asInt();
    return size > 0 ? size : 50;
}

void Map::mapUp() { ++currentMap; }

void Map::mapDown() { --currentMap; }

void Map::showAll() {
    hide();
    for (std::set<MapObject *>::iterator it = mapObjects.begin(); it != mapObjects.end(); ++it) {
        (*it)->setMap(this);
        (*it)->setVisible((*it)->getPosZ() == currentMap);
    }
    for (iterator it = begin(); it != end(); ++it) {
        const Coords coords = (*it).first;
        if (coords.z != currentMap)
            continue;
        Tile *tile = Tile::getTile((*it).second, coords.x, coords.y, coords.z);
        tiles.insert(std::pair<Coords, Tile *>(coords, tile));
        tile->addToScene(scene);
    }
}

int Map::getCurrentMap() { return currentMap; }

Map *MapObject::getMap() { return map; }

bool Map::isEditor() { return GameScene::getGame() == 0 || GameScene::getView() == 0; }

void MapObject::mousePressEvent(QGraphicsSceneMouseEvent *event) {
    if (Map::isEditor()) {
        AnimatedObject::mousePressEvent(event);
        event->accept();
        return;
    }
    event->ignore();
}
