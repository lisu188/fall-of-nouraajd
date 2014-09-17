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
	virtual ~CGameScene();
	void playerMove ( int dirx, int diry );
	void startGame ( QString file ,QString player );
	CPlayer *getPlayer() const;
	void setPlayer ( CPlayer *value );
	CMap *getMap() const;
	void setMap ( CMap *value );
	CGameView *getView();
protected:
	void keyPressEvent ( QKeyEvent *keyEvent );

private:
	CMap *map;
	CPlayer *player;
};

