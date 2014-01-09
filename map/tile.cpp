#include "tile.h"

#include <view/gamescene.h>
#include <view/mapscene.h>
#include <configuration/configurationprovider.h>
#include <destroyer/destroyer.h>

std::unordered_map<std::string,std::function<void()>> Tile::steps
{
    {"RoadTile",&RoadTile}
};

Tile::Tile(std::string name, int x, int y, int z) {
    this->setZValue(0);
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

std::string Tile::getRandomTile()
{
    return "GrassTile";
}

Tile *Tile::getTile(std::string type,int x,int y,int z)
{
    return new Tile(type,x,y,z);
}

void Tile::addToScene(QGraphicsScene *scene)
{
    if(dynamic_cast<MapScene*>(scene))
    {
        this->QGraphicsPixmapItem::setAcceptDrops(true);
        size=dynamic_cast<MapScene*>(scene)->getMap()->getTileSize();
    }
    else {
        size=dynamic_cast<GameScene*>(scene)->getMap()->getTileSize();
    }
    Json::Value config=(*ConfigurationProvider::getConfig("config/tiles.json"))[className];
    loadFromJson(config);
    setPos(posx*size,posy*size);
    scene->addItem(this);
}

void Tile::removeFromScene(QGraphicsScene *scene)
{
    scene->removeItem(this);
}

void Tile::loadFromJson(Json::Value config)
{
    step=config.get("canStep",true).asBool();
    setAnimation(config.get("path","").asCString(),size);
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
    //tu supress dragging
}

void Tile::dropEvent(QGraphicsSceneDragDropEvent *event)
{
    MapObject *object=(MapObject*)event->source();
    event->acceptProposedAction();
    object->moveTo(posx,posy,posz,true);
}


void RoadTile()
{
    GameScene::getPlayer()->heal(1);
}
