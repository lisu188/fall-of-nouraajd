#ifndef GAMESCENE_H
#define GAMESCENE_H

#include <QGraphicsScene>
#include <QGraphicsSceneMouseEvent>
#include <QKeyEvent>
#include "map/map.h"
#include <list>
#include <random>
#include <time.h>

#include <creatures/player.h>

class GameView;
class FightView;
class GameScene : public QGraphicsScene
{

public:
    GameScene();
    ~GameScene();
    static Player* getPlayer();
    static void setPlayer(Player *pla);
    static GameScene* getGame();
    static GameView *getView();
    void playerMove(int dirx, int diry);
    void ensureSize(int sizex, int sizey);

    void changeMap();
protected:
    void keyPressEvent(QKeyEvent *keyEvent);
private:
    Map *map;
    static Player *player;
    static GameScene *game;
    void addRandomTile(int x,int y);
    void addTile(Tile *tile);
    void addObject(MapObject *mapObject);

};

#endif // GAMESCENE_H
