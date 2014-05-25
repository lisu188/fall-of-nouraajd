#ifndef GAMESCENE_H
#define GAMESCENE_H

#include <QGraphicsScene>
#include <QGraphicsSceneMouseEvent>
#include <QKeyEvent>
#include "src/map/map.h"
#include <list>
#include <random>
#include <time.h>

#include <src/creatures/player.h>

class GameView;
class FightView;
class GameScene : public QGraphicsScene
{
    Q_OBJECT
public:
    ~GameScene();
    static Player* getPlayer();
    static void setPlayer(Player *pla);
    static GameScene* getGame();
    static GameView *getView();
    static unsigned int getStep();
    Map *getMap();
    void playerMove(int dirx, int diry);
    void startGame();

protected:
    void keyPressEvent(QKeyEvent *keyEvent);
    virtual void mousePressEvent(QGraphicsSceneMouseEvent *event);
    virtual void mouseMoveEvent(QGraphicsSceneMouseEvent *event);
    virtual void mouseReleaseEvent(QGraphicsSceneMouseEvent *event);
private:
    void adjustStepTimer(QGraphicsSceneMouseEvent *event);
    Map *map;
    static Player *player;
    static GameScene *game;
    void addRandomTile(int x, int y);
    void addTile(Tile *tile);
    void addObject(MapObject *mapObject);
    unsigned int click = 0;
    class StepTimer: public QTimer
    {
    public:
        int getDirx() const;
        void setDirx(int value);

        int getDiry() const;
        void setDiry(int value);

    private:
        int dirx, diry;
    }
    stepTimer;
private slots:
    void clickMove();
};

#endif // GAMESCENE_H
