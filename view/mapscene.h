#ifndef MAPSCENE_H
#define MAPSCENE_H

#include <QGraphicsScene>
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
};

#endif // MAPSCENE_H
