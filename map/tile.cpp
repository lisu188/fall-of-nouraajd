#include "tile.h"

#include <view/gamescene.h>
#include <view/mapscene.h>
#include <configuration/configurationprovider.h>
#include <destroyer/destroyer.h>

std::unordered_map<std::string,std::function<void()>> Tile::steps
{
    {"RoadTile",&RoadTile}
};

Tile::Tile(std::string name, int x, int y, int z) :MapObject(x,y,z,0) {
    className=name;
    setXYZ(x,y,z);
}

Tile::~Tile()
{
    for(std::list<Event *>::iterator it=events.begin(); it!=events.end(); it++)
    {
        delete *it;
    }
    events.clear();
}

void Tile::moveTo(int x, int y, int z, bool silent)
{
    if(init)
    {
        map->erase(map->find(Coords(posx,posy,posz)));
        setXYZ(x,y,z);
        map->insert(std::pair<Coords,std::string>(Coords(posx,posy,posz),className));
    }
    MapObject::moveTo(x,y,z,silent);
    init =true;
}

Coords Tile::getCoords()
{
    return Coords(posx,posy,posz);
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

Tile *Tile::getTile(std::string type,int x,int y,int z)
{
    return new Tile(type,x,y,z);
}

void Tile::addToScene(QGraphicsScene *scene)
{
    Json::Value config=(*ConfigurationProvider::getConfig("config/tiles.json"))[className];
    loadFromJson(config);
    setPos(posx*getSize(),posy*getSize());
    if(dynamic_cast<MapScene*>(scene))
    {
        this->setDraggable();
        MapObject::setMap(dynamic_cast<MapScene*>(scene)->getMap());
    }
    else {
        MapObject::setMap(dynamic_cast<GameScene*>(scene)->getMap());
    }
}

void Tile::removeFromScene(QGraphicsScene *scene)
{
    scene->removeItem(this);
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

void Tile::setXYZ(int x, int y, int z)
{
    posx=x;
    posy=y;
    posz=z;
}

void Tile::mousePressEvent(QGraphicsSceneMouseEvent *event)
{
    if(draggable)
    {
        AnimatedObject::mousePressEvent(event);
    }
}

void Tile::setMap(Map *map)
{
    this->map=map;
    addToScene(map->getScene());
}

void RoadTile()
{
    GameScene::getPlayer()->heal(1);
}
