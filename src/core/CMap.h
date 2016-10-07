#pragma once

#include "core/CGlobal.h"

#include "core/CUtil.h"
#include "handler/CHandler.h"
#include "core/CProvider.h"
#include "CPlugin.h"


class CGame;

class CTile;

class CPlayer;

class CLootHandler;

class CInteraction;

class CObjectHandler;

class CScriptHandler;

class CEventHandler;

class CMapObject;

//TODO: triggers saving
class CMap : public CGameObject {
    friend class CMapLoader;
V_META(CMap,CGameObject, V_PROPERTY(CMap, int, turn, getTurn, setTurn),
       V_PROPERTY(CMap, std::set<std::shared_ptr<CMapObject>>, objects, getObjects, setObjects),
       V_PROPERTY(CMap, std::set<std::shared_ptr<CTile>>, tiles, getTiles, setTiles))
public:
    CMap();
    CMap(std::shared_ptr<CGame> game);

    bool addTile(std::shared_ptr<CTile> tile, int x, int y, int z);

    void removeTile(int x, int y, int z);

    void move();

    std::shared_ptr<CTile> getTile(int x, int y, int z);

    std::shared_ptr<CTile> getTile(Coords coords);

    bool contains(int x, int y, int z);

    void addObject(std::shared_ptr<CMapObject> mapObject);

    void removeObject(std::shared_ptr<CMapObject> mapObject);

    std::shared_ptr<CGame> getGame() const;

    void mapUp();

    void mapDown();

    int getCurrentMap();

    int getEntryX();

    int getEntryY();

    int getEntryZ();

    void ensureTile(int i, int j);

    std::map<int, std::pair<int, int> > getBounds();

    int getCurrentXBound();

    int getCurrentYBound();

    void removeObjectByName(std::string name);

    std::string addObjectByName(std::string name, Coords coords);

    void replaceTile(std::string name, Coords coords);

    Coords getLocationByName(std::string name);

    std::shared_ptr<CPlayer> getPlayer();

    void setPlayer(std::shared_ptr<CPlayer> player);

    void moveTile(std::shared_ptr<CTile> tile, int x, int y, int z);

    std::shared_ptr<CLootHandler> getLootHandler();

    std::shared_ptr<CObjectHandler> getObjectHandler();

    std::shared_ptr<CEventHandler> getEventHandler();

    bool canStep(int x, int y, int z);

    bool canStep(const Coords &coords);

    std::shared_ptr<CMapObject> getObjectByName(std::string name);

    bool isMoving();

//    void applyEffects();

    void forObjects(std::function<void(std::shared_ptr<CMapObject>)> func,
                    std::function<bool(std::shared_ptr<CMapObject>)> predicate = [](
                            std::shared_ptr<CMapObject>) { return true; });

    void forTiles(std::function<void(std::shared_ptr<CTile>)> func,
                  std::function<bool(std::shared_ptr<CTile>)> predicate = [](std::shared_ptr<CTile>) { return true; });

    void removeObjects(std::function<bool(std::shared_ptr<CMapObject>)> func);

    template<typename T>
    std::shared_ptr<T> createObject(std::string name) {
        return getObjectHandler()->createObject<T>(this->ptr<CMap>(), name);
    }


    void load_plugin(std::function<std::shared_ptr<CMapPlugin>()> plugin);

    int getTurn();

    void setTurn(int turn);

    std::set<std::shared_ptr<CMapObject>> getObjects();

    void setObjects(std::set<std::shared_ptr<CMapObject>> objects);

    std::set<std::shared_ptr<CTile>> getTiles();

    void setTiles(std::set<std::shared_ptr<CTile>> objects);
private:
    void resolveFights();

    std::unordered_map<std::string, std::shared_ptr<CMapObject>> mapObjects;
    std::unordered_map<Coords, std::shared_ptr<CTile>> tiles;

    std::weak_ptr<CGame> game;
    std::shared_ptr<CPlayer> player;
    int currentLevel = 0;
    std::map<int, std::string> defaultTiles;
    std::map<int, std::pair<int, int> > boundaries;
    int entryx, entryz, entryy;
    vstd::lazy<CLootHandler, std::shared_ptr<CMap>> lootHandler;
    vstd::lazy<CObjectHandler, std::shared_ptr<CObjectHandler>> objectHandler;
    vstd::lazy<CEventHandler> eventHandler;
    int turn = 0;
    bool moving = false;
};

