#ifndef GAMESCENE_H
#define GAMESCENE_H
#include <QGraphicsScene>
#include "Python.h"
#include <QGraphicsSceneMouseEvent>
#include <QKeyEvent>
#include "map.h"
#include <list>
#include <random>
#include <time.h>
#include "player.h"
#include <QDateTime>

class GameView;
class FightView;
class GameScene : public QGraphicsScene {
	Q_OBJECT
public:
	void playerMove ( int dirx, int diry );
	void startGame ( std::string file ,std::string player );
	Player *getPlayer() const;
	void setPlayer ( Player *value );
	Map *getMap() const;
	void setMap ( Map *value );
	GameView *getView();

protected:
	void keyPressEvent ( QKeyEvent *keyEvent );
	virtual void mousePressEvent ( QGraphicsSceneMouseEvent *event );
	virtual void mouseMoveEvent ( QGraphicsSceneMouseEvent *event );
	virtual void mouseReleaseEvent ( QGraphicsSceneMouseEvent *event );

private:
	Map *map;
	Player *player;
};

#endif // GAMESCENE_H
