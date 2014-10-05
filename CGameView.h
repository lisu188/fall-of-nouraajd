#pragma once

#include "CGameScene.h"
#include "CPlayerView.h"
#include <QGraphicsView>
#include <QThread>
#include "CPlayerView.h"
#include "CGamePanel.h"

class CPlayer;
class CGameView : public QGraphicsView {
	Q_OBJECT
public:
	CGameView ( QString mapName,QString playerType );
	virtual ~CGameView();
	void start();
	CGameScene *getScene() const;
	void setScene ( CGameScene *value );
	void centerOn ( CPlayer *player );
	Q_INVOKABLE void show();
protected:
	virtual void mouseDoubleClickEvent ( QMouseEvent *e );
	virtual void resizeEvent ( QResizeEvent *event );
	virtual void wheelEvent ( QWheelEvent * );
	virtual void dragMoveEvent ( QDragMoveEvent *e );
private:
	CGameScene *scene;
	static bool init;
	QTimer timer;
	PlayerStatsView playerStatsView;
	QString mapName;
	QString playerType;

};

