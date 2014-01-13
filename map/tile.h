#ifndef TILE_H
#define TILE_H

#include <QGraphicsPixmapItem>
#include <map/coords.h>
#include <map/events/event.h>
#include <map/map.h>
#include <json/json.h>
#include <unordered_map>
#include <string>
#include <functional>

class Tile : public MapObject
{
public:

    Tile(std::string name,int x,int y,int z);

    ~Tile();

    void moveTo(int x, int y, int z, bool silent=false);

    Coords getCoords();

    void move(int x,int y);

    void onStep();

    bool canStep() const;

    static Tile *getTile(std::string type, int x, int y,int z);

    void addToScene(QGraphicsScene *scene);
    void removeFromScene(QGraphicsScene *scene);

    std::string className;

    void loadFromJson(Json::Value config);
    Json::Value saveToJson();

    void setDraggable() {
        draggable=true;
    }
protected:
    bool step;

private:
    void setXYZ(int x, int y,int z);

    std::list<Event*> events;

    bool draggable=false;

    static std::unordered_map<std::string,std::function<void()>> steps;

protected:
    virtual void mousePressEvent(QGraphicsSceneMouseEvent *event);

public:
    virtual void onEnter() {}
    virtual void onMove() {}
    virtual bool canSave() {
        return false;
    }

    void setMap(Map *map);
private:
    bool init=false;
};

void RoadTile();
#endif // TILE_H
