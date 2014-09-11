#pragma once
#include <QGraphicsPixmapItem>
#include <QTimer>
#include <QWidget>
class CAnimation;
class CAnimatedObject : public QObject, public QGraphicsPixmapItem {
	Q_OBJECT
	Q_PROPERTY ( QString animation READ getAnimation WRITE setAnimation USER true )
public:
	CAnimatedObject();
	virtual ~CAnimatedObject();
	QPointF mapToParent ( int a, int b );
	void setAnimation ( QString path );
	QString getAnimation();
protected:
	CAnimation *staticAnimation;
	virtual void mousePressEvent ( QGraphicsSceneMouseEvent * );
private:
	QString path;
	QTimer *timer;
	Q_SLOT void animate();
};
