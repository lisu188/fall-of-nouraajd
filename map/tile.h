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

    Tile(std::string name,int x,int y,int z);

    ~Tile();

    Coords getCoords();

    bool isOn(int x,int y);

    void move(int x,int y);

    void onStep();

    static int size;

    bool canStep() const;

    static std::string getRandomTile();
    static Tile *getTile(std::string type, int x, int y,int z);

    void addToGame();
    void removeFromGame();

    std::string className;

    void loadFromJson(Json::Value config);
    Json::Value saveToJson();



protected:
    bool step;

private:
    void setXYZ(int x, int y,int z);

    std::list<Event*> events;

    int posx;
    int posy;
    int posz;

    static std::unordered_map<std::string,std::function<void()>> steps;
};

void RoadTile();
#endif // TILE_H
