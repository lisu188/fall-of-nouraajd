#ifndef MAPSCENE_H
#define MAPSCENE_H

#include <QDragMoveEvent>
#include <QGraphicsScene>
#include <QGraphicsSceneDragDropEvent>

class Map;
class MapScene  : public QGraphicsScene
{
public:
    MapScene();
    ~MapScene();
    Map *getMap() {
        return map;
    }
private:
    Map *map;

    // QGraphicsScene interface
protected:
    virtual void keyPressEvent(QKeyEvent *event);
    void dropEvent(QGraphicsSceneDragDropEvent *event);
};

#endif // MAPSCENE_H
