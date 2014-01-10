#ifndef MAP_H
#define MAP_H

#include "map/coords.h"
#include <list>
#include <QTimer>
#include <QObject>
#include <qgraphicsitemanimation.h>
#include <QTimeLine>
#include <animation/animation.h>
#include <animation/animatedobject.h>
#include <unordered_map>
#include <json/json.h>

class MapObject;
class Tile;
class Player;

class Map : public std::unordered_map<Coords,std::string,CoordsHasher>
{
public:
    Map(QGraphicsScene *scene);
    ~Map();
    void move(int x,int y);
    std::string getTile(int x, int y, int z);
    bool contains(int x, int y, int z);
    void addObject(MapObject *mapObject);

    void addRiver(int length, int startx, int starty, int startz);
    void addRoad(int length, int startx, int starty, int startz);
    void addDungeon(Coords enter, Coords exit, int width, int height);

    void removeObject(MapObject *mapObject);

    void loadMapFromJson(Json::Value config);
    Json::Value saveMapToJson();

    void loadFromJson(Json::Value config);
    Json::Value saveToJson();

    void ensureSize(Player *player);
    void hide();
    void show();
    Json::Value saveStateToJson();
    void loadStateFromJson(Json::Value config);
    QGraphicsScene *getScene() const;
    void showAll();

    void mapUp();
    void mapDown();

    int getTileSize() const;
    void setTileSize(int value);

    int getCurrentMap();
private:
    std::list<MapObject*> mapObjects;
    void randomDir(int *tab, int rule);
    bool addTile(std::string name, int x, int y, int z);
    std::map<Coords,Tile *> tiles;
    int cacheSize=25;
    QGraphicsScene *scene;
    int currentMap=0;
    int tileSize;
    std::map<int,std::string> defaultTiles;
};

class MapObject : protected AnimatedObject
{
public:
    MapObject(int x, int y,int z, int v);
    ~MapObject();
    int posx,posy,posz;
    virtual void moveTo(int x, int y, int z, bool silent=false);

    int getPosX() const;
    int getPosY() const;
    int getPosZ() const;

    void removeFromGame();

    virtual void onEnter()=0;
    virtual void onMove()=0;

    void move(int x, int y);

    void setParentItem(QGraphicsItem *parent);

    virtual void loadFromJson(Json::Value config)=0;
    virtual Json::Value saveToJson()=0;
    virtual bool canSave()=0;

    virtual void setMap(Map *map);
    Map *getMap();
    void setVisible(bool vis);
    int getSize();
protected:
    void setAnimation(std::string path);
    Map *map=0;
    QGraphicsItemAnimation *animation;
    QTimeLine *timer;
    QGraphicsSimpleTextItem statsView;
private:
    std::string path;
public:
    std::string className;
};

#endif // MAP_H
