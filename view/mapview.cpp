#include "mapscene.h"
#include "mapview.h"
#include <map/tile.h>
#include <QKeyEvent>
#include <map/map.h>
#include <QGraphicsSceneDragDropEvent>
#include <configuration/configurationprovider.h>


MapView::MapView()
{
    showFullScreen();
    setViewportUpdateMode(QGraphicsView::BoundingRectViewportUpdate);
    setWindowState(Qt::WindowNoState);
    scene=new MapScene();
    setScene(scene);
    setAcceptDrops(true);
    Json::Value config=*ConfigurationProvider::getConfig("config/items.json");
    Json::Value::iterator it=config.begin();
    for(; it!=config.end(); it++)
    {
        std::string name=it.memberName();
        Item*item=Item::getItem(name.c_str());
        if(item) {
            items.push_back(item);
            item->setMap(scene->getMap());
        }
    }
    itemsList=new PlayerListView((std::list<ListItem *> *)&items);
    scene->addItem(itemsList);
    itemsList->setPos(mapToScene(0,0));
    itemsList->update();
}

MapView::~MapView()
{
    delete scene;
}

void MapView::dragMoveEvent(QDragMoveEvent *event)
{
    QGraphicsView::dragMoveEvent(event);
    event->acceptProposedAction();
}


