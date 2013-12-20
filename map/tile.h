#ifndef TILE_H
#define TILE_H
#include <QGraphicsPixmapItem>
#include <animation/animatedobject.h>
#include <map/coords.h>
#include "map/events/event.h"
#include <json/json.h>
#include <unordered_map>
#include <string>
#include <functional>

class Tile : protected AnimatedObject
{
public:

    Tile(std::string name,int x,int y);

    ~Tile();

    Coords getCoords();

    bool isOn(int x,int y);

    void move(int x,int y);

    void onStep();

    static int size;

    bool canStep() const;

    static Tile *getRandomTile(int x, int y);
    static Tile *getTile(std::string type, int x, int y);

    void addToGame();
    void removeFromGame();

    std::string className;

    void loadFromJson(Json::Value config);
    Json::Value saveToJson();



protected:
    bool step;

private:
    void setXY(int x, int y);

    std::list<Event*> events;

    int posx;
    int posy;

    static std::unordered_map<std::string,std::function<void()>> steps;
};

void RoadTile();
#endif // TILE_H
