#include "gamescene.h"
#include "scrollobject.h"

#include <src/playerlistview.h>

#include "CConfigurationProvider.h"

ScrollObject::ScrollObject ( PlayerListView *stats, bool isRight ) {
	this->isRight = isRight;
	this->setZValue ( 1 );
	this->stats = stats;
	int size = CMap::getTileSize();
	if ( !isRight ) {
		this->setAnimation ( "images/arrows/left/", size );
	} else {
		this->setAnimation ( "images/arrows/right/", size );
	}
	setParentItem ( stats );
}

void ScrollObject::setVisible ( bool visible ) {
	if ( visible && this->scene() != stats->scene() ) {
		stats->scene()->addItem ( this );
	}
	QGraphicsItem::setVisible ( visible );
}

void ScrollObject::mousePressEvent ( QGraphicsSceneMouseEvent *event ) {
	if ( isRight ) {
		stats->updatePosition ( 1 );
	}
	if ( !isRight ) {
		stats->updatePosition ( -1 );
	}
}
