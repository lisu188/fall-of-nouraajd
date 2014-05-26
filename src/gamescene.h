#ifndef GAMESCENE_H
#define GAMESCENE_H

#include <QGraphicsScene>
#include <QGraphicsSceneMouseEvent>
#include <QKeyEvent>
#include "src/map.h"
#include <list>
#include <random>
#include <time.h>
#include <src/player.h>

class GameView;
class FightView;
class GameScene : public QGraphicsScene
{
    Q_OBJECT
public:
    static Player* getPlayer();
    static void setPlayer(Player *pla);
    static GameScene* getGame();
    static GameView *getView();
    static unsigned int getStep();
    static Map *getMap();
    void playerMove(int dirx, int diry);
    void startGame();
protected:
    void keyPressEvent(QKeyEvent *keyEvent);
    virtual void mousePressEvent(QGraphicsSceneMouseEvent *event);
    virtual void mouseMoveEvent(QGraphicsSceneMouseEvent *event);
    virtual void mouseReleaseEvent(QGraphicsSceneMouseEvent *event);
private:
    void adjustStepTimer(QGraphicsSceneMouseEvent *event);
    static Map *map;
    static Player *player;
    static GameScene *game;
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
