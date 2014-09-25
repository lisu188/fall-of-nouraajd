#ifndef GAMEVIEW_H
#define GAMEVIEW_H
#include "CGameScene.h"
#include "CPlayerView.h"
#include <QGraphicsView>
#include <QThread>
#include "CPlayerView.h"
#include "CGamePanel.h"


class CGameView : public QGraphicsView {
	Q_OBJECT
public:
	CGameView ( QString mapName,QString playerType );
	virtual ~CGameView();

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
	static bool init;
	QTimer timer;
	QGraphicsPixmapItem loading;
	PlayerStatsView playerStatsView;
	QString mapName;
	QString playerType;

};
#endif // GAMEVIEW_H
