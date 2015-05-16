#pragma once
#include <QGraphicsScene>
#include <QGraphicsSceneMouseEvent>
#include <QKeyEvent>
#include <list>
#include <random>
#include <time.h>
#include <QDateTime>

class CGameView;
class CPlayer;
class CMap;
class CMapObject;
class CGame : public QGraphicsScene {
    Q_OBJECT
public:
    CGame ( QObject *parent );
    virtual ~CGame();
    void startGame ( QString file ,QString player );
    void changeMap ( QString file );
    CMap *getMap() const;
    CGameView *getView();
    void removeObject ( CMapObject *object );
protected:
    virtual void keyPressEvent ( QKeyEvent *event );
private:
    CMap *map=0;
};

