#include "mapscene.h"
#include "mapview.h"
#include <map/tile.h>
#include <QKeyEvent>
#include <map/map.h>
#include <QGraphicsSceneDragDropEvent>
#include <configuration/configurationprovider.h>
#include <buildings/building.h>
#include <QDebug>

extern std::set<int> qMetaTypesRegister;

void MapView::loadItems()
{
    Json::Value config=*ConfigurationProvider::getConfig("config/items.json");
    Json::Value::iterator it=config.begin();
    for(; it!=config.end(); it++)
    {
        std::string name=it.memberName();
        Item*item=Item::getItem(name.c_str());
        if(item) {
            items.insert(item);
            //item->setMap(scene->getMap());
        }
    }
}

void MapView::loadBuildings()
{
    for(std::set<int>::iterator it=qMetaTypesRegister.begin(); it!=qMetaTypesRegister.end(); it++)
    {
        QObject *object=(QObject*)QMetaType::create(*it);
        if(object->inherits("Building")&&*it!=QMetaType::type("Building"))
        {
            buildings.insert((Building*)object);
            //((Building*)object)->setMap(scene->getMap());
        }
        else
        {
            delete object;
        }
    }
}

MapView::MapView()
{
    showFullScreen();
    setViewportUpdateMode(QGraphicsView::BoundingRectViewportUpdate);
    setWindowState(Qt::WindowNoState);
    scene=new MapScene();
    setScene(scene);
    setAcceptDrops(true);
    loadItems();
    loadBuildings();
    itemsList=new PlayerListView((std::set<ListItem *,Comparer> *)&items);
    itemsList->setAcceptDrops(false);
    scene->addItem(itemsList);
    itemsList->setDraggable();
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
    if(event->source()==itemsList)
    {
        itemsList->setPos(this->mapToScene(event->pos()));
    }
    event->acceptProposedAction();
}

void MapView::dropEvent(QDropEvent *event)
{
    if(event->source()!=itemsList)
    {
        QGraphicsView::dropEvent(event);
        ListItem *item=(ListItem*)(event->source());
        auto list=itemsList->getItems();
        if(list->find(item)!=list->end())
        {
            list->erase(list->find(item));
            if(item->inherits("Item"))
            {
                item=Item::getItem(item->className);
            }
            else
            {
                item=(ListItem*)QMetaType::create(QMetaType::type(item->metaObject()->className()));
            }
            if(item) {
                list->insert(item);
            }
            //item->setMap(scene->getMap());
            itemsList->update();
        }
    }
}

void MapView::keyPressEvent(QKeyEvent *e)
{
    QGraphicsView::keyPressEvent(e);
    if(e->key()==Qt::Key_Space)
    {
        if(itemsList->getItems()==&items)
        {
            itemsList->setItems(&buildings);
        }
        else
        {
            itemsList->setItems(&items);
        }
    }
}
