#pragma once
#include <QGraphicsPixmapItem>
#include <QTimer>
#include <QWidget>
class CAnimation;
class CAnimatedObject : public QObject, protected QGraphicsPixmapItem {
	Q_OBJECT
	Q_PROPERTY ( QString animation READ getAnimation WRITE setAnimation USER true )

	friend class CGameScene;
	friend class CGameView;
	friend class CPlayerListView;
	friend class CItemSlot;
public:
	CAnimatedObject();
	virtual ~CAnimatedObject();
	QPointF mapToParent ( int a, int b );
	void setAnimation ( QString path );
	QString getAnimation();
private:
	QString path;
	QTimer *timer;
	CAnimation *staticAnimation;
	void animate();
};
