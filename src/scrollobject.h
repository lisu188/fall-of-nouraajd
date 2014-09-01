#include "playerstatsview.h"
#include <QGraphicsSceneMouseEvent>
#include "CAnimatedObject.h"

#ifndef SCROLLOBJECT_H
#define SCROLLOBJECT_H

class PlayerListView;

class ScrollObject : public CAnimatedObject {
public:
	ScrollObject ( PlayerListView *stats, bool isRight );
	void setVisible ( bool visible );

private:
	bool isRight;
	PlayerListView *stats;

protected:
	virtual void mousePressEvent ( QGraphicsSceneMouseEvent *event );
};

#endif // SCROLLOBJECT_H
