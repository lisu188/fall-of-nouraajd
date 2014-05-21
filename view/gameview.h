#ifndef GAMEVIEW_H
#define GAMEVIEW_H

#include <view/charview.h>
#include "gamescene.h"
#include "playerequippedview.h"

#include <QGraphicsView>
#include <QThread>
#include <view/playerstatsview.h>
#include <view/fightview.h>

class BackPackObject: public QWidget {
		Q_OBJECT
	public:
		BackPackObject();
	protected:
		void mousePressEvent(QMouseEvent *);
		void paintEvent(QPaintEvent *event);
	private:
		QPixmap pixmap;
		unsigned int time = 0;signals:
		void clicked();
};

class GameView: public QGraphicsView {
		Q_OBJECT
	public:
		GameView();
		~GameView();
		FightView *getFightView();
		CharView *getCharView();
		void showFightView();
	protected:
		void mouseDoubleClickEvent(QMouseEvent *e);
		void resizeEvent(QResizeEvent *event);
		virtual void wheelEvent(QWheelEvent *);
		virtual void dragMoveEvent(QDragMoveEvent *e);
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
		PlayerEquippedView *playerEquippedView;public slots:
		void showCharView();private slots:
		void start();
};
#endif // GAMEVIEW_H