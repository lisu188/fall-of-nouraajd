#include "mapscene.h"

#include <map/map.h>

#include <configuration/configurationprovider.h>

#include <QKeyEvent>
#include <fstream>
#include <map/tile.h>
#include <json/json.h>

MapScene::MapScene()
{
    map=new Map(this);
    map->loadFromJson(*ConfigurationProvider::getConfig("config/map.json"));
    map->showAll();
}

MapScene::~MapScene()
{
    FILE *infile = fopen("config/map.json", "w+");
    fclose(infile);
    std::fstream jsonFileStream;
    Json::FastWriter writer;
    jsonFileStream.open ("config/map.json");
    jsonFileStream << writer.write(map->saveToJson());
    jsonFileStream.close();
    delete map;
}

void MapScene::keyPressEvent(QKeyEvent *event)
{
    switch(event->key())
    {
    case Qt::Key_Right:
        map->mapUp();
        break;
    case Qt::Key_Left:
        map->mapDown();
        break;
    }
    map->showAll();
}


void MapScene::dropEvent(QGraphicsSceneDragDropEvent *event)
{
    QGraphicsScene::dropEvent(event);
    event->acceptProposedAction();
    MapObject *object=(MapObject*)(event->source());
    Tile *tile=0;
    int posx=event->scenePos().x()/Map::getTileSize();
    int posy=event->scenePos().y()/Map::getTileSize();
    if(!object->inherits("Tile")) {
        map->addObject(object);
    } else
    {
        tile=(Tile*)object;
        if(tile->getMap()==0)
        {
            map->addTile(tile->className,posx,posy,map->getCurrentMap());
            map->showAll();
            return;
        }
    }
    object->setParentItem(0);
    object->moveTo(posx,posy,map->getCurrentMap(),true);
}

