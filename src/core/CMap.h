#pragma once

#include "core/CGlobal.h"

#include "core/CUtil.h"
#include "handler/CHandler.h"
#include "core/CProvider.h"
#include "CPlugin.h"

class CTile;

class CPlayer;


class CInteraction;

class CObjectHandler;

class CScriptHandler;

class CEventHandler;

class CMapObject;

class CTrigger;

class CGame;

class CMap : public CGameObject {
    friend class CMapLoader;

V_META(CMap, CGameObject, V_PROPERTY(CMap, int, turn, getTurn, setTurn),
       V_PROPERTY(CMap, std::set<std::shared_ptr<CMapObject>>, objects, getObjects, setObjects),
       V_PROPERTY(CMap, std::set<std::shared_ptr<CTile>>, tiles, getTiles, setTiles),
       V_PROPERTY(CMap, std::set<std::shared_ptr<CTrigger>>, triggers, getTriggers, setTriggers))
public:
    CMap();


    bool addTile(std::shared_ptr<CTile> tile, int x, int y, int z);

    void removeTile(int x, int y, int z);

    void move();

    std::shared_ptr<CTile> getTile(int x, int y, int z);

    std::shared_ptr<CTile> getTile(Coords coords);

    bool contains(int x, int y, int z);

    void addObject(std::shared_ptr<CMapObject> mapObject);

    void removeObject(std::shared_ptr<CMapObject> mapObject);


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


    std::shared_ptr<CEventHandler> getEventHandler();

    bool canStep(int x, int y, int z);

    bool canStep(Coords coords);

    std::shared_ptr<CMapObject> getObjectByName(std::string name);

    bool isMoving();

//    void applyEffects();

    void forObjects(std::function<void(std::shared_ptr<CMapObject>)> func,
                    std::function<bool(std::shared_ptr<CMapObject>)> predicate = [](
                            std::shared_ptr<CMapObject>) { return true; });

    void forTiles(std::function<void(std::shared_ptr<CTile>)> func,
                  std::function<bool(std::shared_ptr<CTile>)> predicate = [](std::shared_ptr<CTile>) { return true; });

    void removeObjects(std::function<bool(std::shared_ptr<CMapObject>)> func);

    int getTurn();

    void setTurn(int turn);

    std::set<std::shared_ptr<CMapObject>> getObjects();

    void setObjects(std::set<std::shared_ptr<CMapObject>> objects);

    std::set<std::shared_ptr<CTile>> getTiles();

    void setTiles(std::set<std::shared_ptr<CTile>> objects);

    void dumpPaths(std::string path);

    std::set<std::shared_ptr<CTrigger>> getTriggers();

    void setTriggers(std::set<std::shared_ptr<CTrigger>> triggers);

private:
    void resolveFights();

    std::unordered_map<std::string, std::shared_ptr<CMapObject>> mapObjects;
    std::unordered_map<Coords, std::shared_ptr<CTile>> tiles;


    std::shared_ptr<CPlayer> player;
    int currentLevel = 0;
    std::map<int, std::string> defaultTiles;
    std::map<int, std::pair<int, int> > boundaries;
    int entryx = 0;
    int entryz = 0;
    int entryy = 0;

    vstd::lazy<CEventHandler> eventHandler;
    int turn = 0;
    bool moving = false;
};

