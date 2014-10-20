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
class CGameScene : public QGraphicsScene {
	Q_OBJECT
public:
	CGameScene ( QObject *parent );
	virtual ~CGameScene();
	void startGame ( QString file ,QString player );
	CPlayer *getPlayer() const;
	void setPlayer ( CPlayer *value );
	CMap *getMap() const;
	CGameView *getView();
	void removeObject ( CMapObject *object );
protected:
	virtual void keyPressEvent ( QKeyEvent *event );
private:
	CMap *map=0;
	CPlayer *player=0;
};

