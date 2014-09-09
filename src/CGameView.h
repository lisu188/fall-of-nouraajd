#ifndef GAMEVIEW_H
#define GAMEVIEW_H
#include "CGameScene.h"
#include "CPlayerView.h"
#include <QGraphicsView>
#include <QThread>
#include "CPlayerView.h"
#include "CGamePanel.h"

class BackPackObject : public QWidget {
	Q_OBJECT
public:
	BackPackObject();

protected:
	void mousePressEvent ( QMouseEvent * );
	void paintEvent ( QPaintEvent * );

private:
	QPixmap pixmap;
	int time = 0;
	Q_SIGNAL void clicked();
};

class CGameView : public QGraphicsView {
	Q_OBJECT
public:
	CGameView ( QString mapName,QString playerType );
	virtual ~CGameView();
	CFightPanel *getFightView();
	CCharPanel *getCharView();
	void showFightView();
	Q_SLOT void showCharView();
	Q_SLOT void start();
	Q_INVOKABLE void show();

	CGameScene *getScene() const;
	void setScene ( CGameScene *value );

protected:
	void mouseDoubleClickEvent ( QMouseEvent *e );
	void resizeEvent ( QResizeEvent *event );
	virtual void wheelEvent ( QWheelEvent * );
	virtual void dragMoveEvent ( QDragMoveEvent *e );

private:
	CGameScene *scene;
	CFightPanel *fightView;
	CCharPanel *charView;
	static bool init;
	QTimer timer;
	QGraphicsPixmapItem loading;
	BackPackObject backpack;
	PlayerStatsView playerStatsView;
	QString mapName;
	QString playerType;
};
#endif // GAMEVIEW_H
