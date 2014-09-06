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
class CGameScene : public QGraphicsScene {
	Q_OBJECT
public:
	void playerMove ( int dirx, int diry );
	void startGame ( QString file ,QString player );
	CPlayer *getPlayer() const;
	void setPlayer ( CPlayer *value );
	CMap *getMap() const;
	void setMap ( CMap *value );
	CGameView *getView();

protected:
	void keyPressEvent ( QKeyEvent *keyEvent );
	virtual void mousePressEvent ( QGraphicsSceneMouseEvent *event );
	virtual void mouseMoveEvent ( QGraphicsSceneMouseEvent *event );
	virtual void mouseReleaseEvent ( QGraphicsSceneMouseEvent *event );

private:
	CMap *map;
	CPlayer *player;
};

