#ifndef MAPVIEW_H
#define MAPVIEW_H

#include <QGraphicsView>
#include <QThread>
class MapScene;

class MapView : public QGraphicsView
{
public:
    MapView();
    ~MapView();
private:
    MapScene *scene;
};

#endif // MAPVIEW_H
