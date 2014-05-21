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
#include <view/listitem.h>

class Tile : public ListItem
{
    Q_OBJECT
public:
    Tile(std::string name,int x=0,int y=0,int z=0);
    Tile();
    Tile(const Tile &tile);
    ~Tile();
    void moveTo(int x, int y, int z, bool silent=false);
    Coords getCoords();
    void move(int x,int y);
    void onStep();
    bool canStep() const;
    static Tile *getTile(std::string type, int x, int y,int z);
    void addToScene(QGraphicsScene *scene);
    void removeFromScene(QGraphicsScene *scene);
    void loadFromJson(Json::Value config);
    Json::Value saveToJson();
    void setDraggable();
    virtual void onEnter() {}
    virtual void onMove() {}
    virtual bool canSave();
    void setMap(Map *map);
protected:
    bool step;
    virtual void mousePressEvent(QGraphicsSceneMouseEvent *event);
private:
    void setXYZ(int x, int y,int z);
    std::list<Event*> events;
    bool draggable=false;
    static std::unordered_map<std::string,std::function<void()>> steps;
    bool init=false;
};
Q_DECLARE_METATYPE(Tile)
void RoadTile();
#endif // TILE_H
