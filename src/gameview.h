#ifndef GAMEVIEW_H
#define GAMEVIEW_H

#include <src/charview.h>
#include "gamescene.h"
#include "playerequippedview.h"

#include <QGraphicsView>
#include <QThread>
#include <src/playerstatsview.h>
#include <src/fightview.h>

class BackPackObject : public QWidget {
	Q_OBJECT
public:
	BackPackObject();

protected:
	void mousePressEvent ( QMouseEvent * );
	void paintEvent ( QPaintEvent *event );

private:
	QPixmap pixmap;
	unsigned int time = 0;
	Q_SIGNAL void clicked();
};

class GameView : public QGraphicsView {
	Q_OBJECT
public:
	GameView ( std::string mapName,std::string playerType );
	~GameView();
	FightView *getFightView();
	CharView *getCharView();
	void showFightView();
	Q_SLOT void showCharView();
	Q_SLOT void start();
	Q_INVOKABLE void show();

protected:
	void mouseDoubleClickEvent ( QMouseEvent *e );
	void resizeEvent ( QResizeEvent *event );
	virtual void wheelEvent ( QWheelEvent * );
	virtual void dragMoveEvent ( QDragMoveEvent *e );

private:
	GameScene *scene;
	FightView *fightView;
	CharView *charView;
	static bool init;
	QTimer timer;
	QGraphicsPixmapItem loading;
	BackPackObject backpack;
	PlayerStatsView playerStatsView;
	PlayerListView *playerInventoryView;
	PlayerListView *playerSkillsView;
	PlayerEquippedView *playerEquippedView;
	std::string mapName;
	std::string playerType;
};
#endif // GAMEVIEW_H
