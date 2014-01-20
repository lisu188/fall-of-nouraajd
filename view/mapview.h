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
private:
    MapScene *scene;
    std::set<Item *> items;
    PlayerListView *itemsList;
protected:
    void dragMoveEvent(QDragMoveEvent *event);


    // QWidget interface
protected:
    virtual void dropEvent(QDropEvent *event);
};

#endif // MAPVIEW_H
