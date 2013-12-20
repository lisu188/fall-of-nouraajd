#include "tile.h"

#include <view/gamescene.h>
#include <configuration/configurationprovider.h>
#include <destroyer/destroyer.h>

int Tile::size=50;

std::unordered_map<std::string,std::function<void()>> Tile::steps
{
    {"RoadTile",&RoadTile}
};

Tile::Tile(std::string name, int x, int y) {
    this->setZValue(0);
    className=name;
    Json::Value config=(*ConfigurationProvider::getConfig("config/tiles.json"))[className];
    loadFromJson(config);
    setXY(x,y);
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
    if(steps.find(className)!=steps.end())
    {
        steps[className]();
    }
}

bool Tile::canStep() const
{
    return step;
}

Tile *Tile::getRandomTile(int x, int y)
{
    return new Tile("GrassTile",x,y);
    switch(rand()%4)
    {
    case 0:
    case 1:
        if(rand()%20==0) {
            return new Tile("MountainTile",x,y);
        }
        else {
            return new Tile("GrassTile",x,y);
        }
    case 2:
        return new Tile("GroundTile",x,y);
    case 3:
        return new Tile("GroundTile",x,y);
    }
    return 0;
}

Tile *Tile::getTile(std::string type,int x,int y)
{
    return new Tile(type,x,y);
}

void Tile::addToGame()
{
    GameScene::getGame()->addItem(this);
}

void Tile::removeFromGame()
{
    GameScene::getGame()->removeItem(this);
}

void Tile::loadFromJson(Json::Value config)
{
    step=config.get("canStep",true).asBool();
    setAnimation(config.get("path","").asCString());
}

Json::Value Tile::saveToJson()
{
    Json::Value config;
    config[(unsigned int)0]=posx;
    config[(unsigned int)1]=posy;
    return config;
}

void Tile::setXY(int x, int y)
{
    posx=x;
    posy=y;
    setPos(x*size,y*size);
}


void RoadTile()
{
    GameScene::getPlayer()->heal(1);
}
