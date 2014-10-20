#include "CEventHandler.h"
#include "CMap.h"
#include "CMapObject.h"

#include <QMetaEnum>
#include <QDebug>

CEventHandler::CEventHandler ( CMap *map ) {
	this->setParent ( map );
	this->map=map;
}

void CEventHandler::gameEvent ( CGameEvent *event, CMapObject *mapObject ) const {
	switch ( event->getType() ) {
	case CGameEvent::onEnter:
		dynamic_cast<Visitable*> ( mapObject )->onEnter ( event );
		break;
	case CGameEvent::onLeave:
		dynamic_cast<Visitable*> ( mapObject )->onLeave ( event );
		break;
	case CGameEvent::onMove:
		mapObject->onMove ( event );
		break;
	case CGameEvent::onDestroy:
		mapObject->onDestroy ( event );
		break;
	case CGameEvent::onCreate:
		mapObject->onCreate ( event );
		break;
	}
	delete event;
}


CGameEvent::CGameEvent ( CGameEvent::Type type, CMapObject *cause ) :type ( type ),cause ( cause ) {

}

CGameEvent::Type CGameEvent::getType() const {
	return type;
}
CMapObject *CGameEvent::getCause() const {
	return cause;
}



