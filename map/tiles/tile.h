#include <QGraphicsPixmapItem>
#include <animation/animatedobject.h>
#include <map/coords.h>
#include "map/events/event.h"

#ifndef TILE_H
#define TILE_H

class Tile : protected AnimatedObject
{
public:

    Tile(int x,int y);

    ~Tile();

    Coords getCoords();

    bool isOn(int x,int y);

    void move(int x,int y);

    virtual void onStep();

    static int size;

    bool canStep() const;

    static Tile *getRandomTile(int x, int y);

    void addToGame();

protected:
    bool step;
    void mousePressEvent(QGraphicsSceneMouseEvent *event);

private:
    void setXY(int x, int y);

    std::list<Event*> events;

    int posx;
    int posy;


};

#endif // TILE_H
