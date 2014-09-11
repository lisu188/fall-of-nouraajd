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
	void showPanel ( QString panel );
	AGamePanel *getPanel ( QString panel );
	Q_SLOT void start();
	Q_INVOKABLE void show();
	CGameScene *getScene() const;
	void setScene ( CGameScene *value );
	void initPanels();
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
	std::map<QString,AGamePanel*> panels;
};
#endif // GAMEVIEW_H
