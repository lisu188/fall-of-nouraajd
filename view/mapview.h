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
    void loadCreatures();
private:
    MapScene *scene;
    std::set<ListItem *,Comparer> items;
    std::set<ListItem *,Comparer> buildings;
    std::set<ListItem *,Comparer> creatures;
    PlayerListView *itemsList;
protected:
    void dragMoveEvent(QDragMoveEvent *event);
    virtual void dropEvent(QDropEvent *event);
    void keyPressEvent(QKeyEvent *e);
};

#endif // MAPVIEW_H
