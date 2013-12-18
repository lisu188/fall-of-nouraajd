#include "grasstile.h"
#include "groundtile.h"
#include "mountaintile.h"
#include "roadtile.h"
#include "tile.h"
#include "watertile.h"

#include <view/gamescene.h>

int Tile::size=50;

Tile::Tile(int x, int y) {
    this->setZValue(0);
    setXY(x,y);
    step=true;
}

Tile::~Tile()
{
    for(std::list<Event *>::iterator it=events.begin(); it!=events.end(); it++)
    {
        delete *it;
    }
    events.clear();
}

Coords Tile::getCoords()
{
    return Coords(posx,posy);
}

bool Tile::isOn(int x, int y)
{
    return posx==x&&posy==y;
}

void Tile::onStep()
{
    for(std::list<Event *>::iterator it=events.begin(); it!=events.end(); it++)
    {
        (*it)->onCall();
    }
}

bool Tile::canStep() const
{
    return step;
}

Tile *Tile::getRandomTile(int x, int y)
{
    return new GrassTile(x,y);
    switch(rand()%4)
    {
    case 0:
    case 1:
        if(rand()%20==0) {
            return new MountainTile(x,y);
        }
        else {
            return new GrassTile(x,y);
        }
    case 2:
        return new GroundTile(x,y);
    case 3:
        return new GroundTile(x,y);
    }
    return 0;
}

Tile *Tile::getTile(std::string type,int x,int y)
{
    if(type.compare("GrassTile")==0)
    {
        return new GrassTile(x,y);
    } else if(type.compare("GroundTile")==0)
    {
        return new GroundTile(x,y);
    } else if(type.compare("RoadTile")==0)
    {
        return new RoadTile(x,y);
    } else if(type.compare("WaterTile")==0)
    {
        return new WaterTile(x,y);
    } else if(type.compare("MountainTile")==0)
    {
        return new MountainTile(x,y);
    }
}

void Tile::addToGame()
{
    GameScene::getGame()->addItem(this);
}

void Tile::loadFromJson(Json::Value config)
{
}

Json::Value Tile::saveToJson()
{
    Json::Value config;
    config["x"]=posx;
    config["y"]=posy;
    return config;
}

void Tile::mousePressEvent(QGraphicsSceneMouseEvent *event)
{
    int x=GameScene::getPlayer()->getPosX()-this->getCoords().first;
    int y=GameScene::getPlayer()->getPosY()-this->getCoords().second;
    if(x==0&&y==0) {
        return;
    }
    if(std::abs(x)>std::abs(y))
    {
        GameScene::getGame()->playerMove(-x/std::abs(x),0);
    }
    else
    {
        GameScene::getGame()->playerMove(0,-y/std::abs(y));
    }
    event->setAccepted(true);
}

void Tile::setXY(int x, int y)
{
    posx=x;
    posy=y;
    setPos(x*size,y*size);
}
