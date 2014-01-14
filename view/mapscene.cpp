#include "mapscene.h"

#include <map/map.h>

#include <configuration/configurationprovider.h>

#include <QKeyEvent>
#include <fstream>
#include <json/json.h>

MapScene::MapScene()
{
    map=new Map(this);
    map->setTileSize(10);
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
    event->acceptProposedAction();
    MapObject *object=(MapObject*)(event->source());
    map->addObject(object);
    object->setParentItem(0);
    int posx=event->scenePos().x()/object->getSize();
    int posy=event->scenePos().y()/object->getSize();
    object->moveTo(posx,posy,object->getPosZ(),true);
}

