#pragma once
#include <QGraphicsPixmapItem>
#include <QTimer>
#include <QWidget>
#include "CAnimation.h"

class CAnimatedObject : public QWidget, public QGraphicsPixmapItem {
	Q_OBJECT
public:
	CAnimatedObject();
	~CAnimatedObject();
	QPointF mapToParent ( int a, int b );

protected:
	CAnimation *staticAnimation;
	void setAnimation ( QString path, int size );
	virtual void mousePressEvent ( QGraphicsSceneMouseEvent * );

private:
	QTimer *timer;
	Q_SLOT void animate();
};
