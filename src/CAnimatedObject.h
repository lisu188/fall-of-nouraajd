#pragma once
#include <QGraphicsPixmapItem>
#include <QTimer>
#include <QWidget>
#include "CAnimation.h"

class CAnimatedObject : public QWidget, public QGraphicsPixmapItem {
	Q_OBJECT
	Q_PROPERTY ( QString animation READ getAnimation WRITE setAnimation USER true )
public:
	CAnimatedObject();
	~CAnimatedObject();
	QPointF mapToParent ( int a, int b );
	void setAnimation ( QString path, int size=50 );
	QString getAnimation();
protected:
	CAnimation *staticAnimation;
	virtual void mousePressEvent ( QGraphicsSceneMouseEvent * );
private:
	QString path;
	QTimer *timer;
	Q_SLOT void animate();
};
