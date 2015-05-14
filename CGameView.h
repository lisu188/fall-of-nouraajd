#pragma once

#include "CGame.h"
#include "CPlayerView.h"
#include <QGraphicsView>
#include <QThread>
#include "panel/CPanel.h"

class CPlayer;
class CGameView : public QGraphicsView {
	Q_OBJECT
public:
	CGameView ( QString mapName,QString playerType );
	virtual ~CGameView();
	void start();
	CGame *getScene() const;
	void centerOn ( CPlayer *player );
	Q_INVOKABLE void show();
protected:
	virtual void mouseDoubleClickEvent ( QMouseEvent *e );
	virtual void resizeEvent ( QResizeEvent *event );
	virtual void wheelEvent ( QWheelEvent * );
	virtual void dragMoveEvent ( QDragMoveEvent *e );
private:
	bool init=false;
	QTimer timer;
	PlayerStatsView playerStatsView;
	QString mapName;
	QString playerType;

};

