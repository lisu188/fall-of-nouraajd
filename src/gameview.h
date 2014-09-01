#ifndef GAMEVIEW_H
#define GAMEVIEW_H
#include "gamescene.h"
#include "playerequippedview.h"
#include <QGraphicsView>
#include <QThread>
#include <src/playerstatsview.h>
#include "gamepanel.h"

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
	FightPanel *getFightView();
	CharPanel *getCharView();
	void showFightView();
	Q_SLOT void showCharView();
	Q_SLOT void start();
	Q_INVOKABLE void show();

	GameScene *getScene() const;
	void setScene ( GameScene *value );

protected:
	void mouseDoubleClickEvent ( QMouseEvent *e );
	void resizeEvent ( QResizeEvent *event );
	virtual void wheelEvent ( QWheelEvent * );
	virtual void dragMoveEvent ( QDragMoveEvent *e );

private:
	GameScene *scene;
	FightPanel *fightView;
	CharPanel *charView;
	static bool init;
	QTimer timer;
	QGraphicsPixmapItem loading;
	BackPackObject backpack;
	PlayerStatsView playerStatsView;
	std::string mapName;
	std::string playerType;
};
#endif // GAMEVIEW_H
