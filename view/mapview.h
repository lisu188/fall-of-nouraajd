#ifndef MAPVIEW_H
#define MAPVIEW_H

#include <view/playerlistview.h>
#include <QGraphicsView>
#include <QThread>
#include <list>

class MapScene;

class MapView : public QGraphicsView
{
public:
    MapView();
    ~MapView();
    void loadItems();
    void loadBuildings();
private:
    MapScene *scene;
    std::set<ListItem *,Comparer> items;
    std::set<ListItem *,Comparer> buildings;
    PlayerListView *itemsList;
protected:
    void dragMoveEvent(QDragMoveEvent *event);
    virtual void dropEvent(QDropEvent *event);
    void keyPressEvent(QKeyEvent *e);
};

#endif // MAPVIEW_H
