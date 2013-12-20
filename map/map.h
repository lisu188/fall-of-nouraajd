#ifndef MAP_H
#define MAP_H

#include "map/coords.h"
#include "tile.h"
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

class Map : private std::unordered_map<Coords,Tile*,CoordsHasher>
{
public:
    ~Map();

    void move(int x,int y);

    Tile *getTile(int x,int y);
    bool contains(int x,int y);
    void addObject(MapObject *mapObject);

    void addRiver(int length, int startx, int starty);
    void addRoad(int length, int startx, int starty);

    void removeObject(MapObject *mapObject);

    void loadFromJson(Json::Value config);
    Json::Value saveToJson();

private:
    std::list<MapObject*> mapObjects;
    void randomDir(int *tab, int rule);
    bool addTile(Tile *tile);
    std::vector<Tile *> tiles;
};

class MapObject : private AnimatedObject
{
public:
    MapObject(Map *map,int x,int y,int z);
    ~MapObject();
    int posx,posy;
    void moveTo(int x, int y,bool silent=false);

    int getPosX() const;
    int getPosY() const;

    void removeFromGame();

    virtual void onEnter()=0;
    virtual void onMove()=0;

    void move(int x, int y);

    void setParentItem(QGraphicsItem *parent);

    virtual void loadFromJson(Json::Value config)=0;
    virtual Json::Value saveToJson()=0;
    virtual bool canSave()=0;
protected:
    void setAnimation(std::string path);
    Map *map;
    QGraphicsItemAnimation *animation;
    QTimeLine *timer;

    QGraphicsSimpleTextItem statsView;
public:
    std::string className;
};

void clearRange(std::vector<Tile *> *vector, int start, int stop);

#endif // MAP_H
