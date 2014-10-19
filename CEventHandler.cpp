#include "CEventHandler.h"
#include "CMap.h"
#include "CMapObject.h"

#include <QMetaEnum>
#include <QDebug>

CEventHandler::CEventHandler ( CMap *map ) {
	this->setParent ( map );
	this->map=map;
}

void CEventHandler::onEnterEvent ( CMapObject *mapObject ) {
	std::set<CMapObject *> objects=map->getIf ( [&mapObject] ( CMapObject *visitor ) {
		return mapObject != visitor && mapObject->getCoords() == visitor->getCoords() ;
	} );
	for ( CMapObject *visitor:objects  ) {
		if ( map->getObjectByName ( mapObject->objectName() ) && map->getObjectByName ( visitor->objectName() ) ) {
			mapObject->setVisitor ( visitor );
			mapObject->onEnter();
			mapObject->setVisitor ( nullptr );
		}
	}
}

void CEventHandler::onMoveEvent ( CMapObject *mapObject ) {
	mapObject->onMove();
}

void CEventHandler::onDestroyEvent ( CMapObject *mapObject ) {
	mapObject->onDestroy();
}

void CEventHandler::onCreateEvent ( CMapObject *mapObject ) {
	mapObject->onCreate();
}

void CEventHandler::onLeaveEvent ( CMapObject *mapObject ) {
	mapObject->onLeave();
}

void CEventHandler::gameEvent ( GameEvent type, CMapObject *mapObject ) {
	switch ( type ) {
	case onEnter:
		onEnterEvent ( mapObject );
		break;
	case onLeave:
		onLeaveEvent ( mapObject );
		break;
	case onMove:
		onMoveEvent ( mapObject );
		break;
	case onDestroy:
		onDestroyEvent ( mapObject );
		break;
	case onCreate:
		onCreateEvent ( mapObject );
		break;
	}

	int enumId=this->metaObject()->indexOfEnumerator ( "GameEvent" );
	QMetaEnum metaEnum = this->metaObject()->enumerator ( enumId );
	qDebug() <<metaEnum.valueToKey ( type ) <<mapObject->getObjectType() <<mapObject->objectName() <<"\n";
}
