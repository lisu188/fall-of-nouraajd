#include "CEventHandler.h"
#include "CMap.h"
#include "CMapObject.h"

#include <QMetaEnum>
#include <QDebug>

CEventHandler::CEventHandler ( CMap *map ) {
	this->setParent ( map );
	this->map=map;
}

void CEventHandler::gameEvent ( CGameEvent *event, CGameObject *mapObject ) const {
	switch ( event->getType() ) {
	case CGameEvent::onEnter:
		dynamic_cast<Visitable*> ( mapObject )->onEnter ( event );
		break;
	case CGameEvent::onLeave:
		dynamic_cast<Visitable*> ( mapObject )->onLeave ( event );
		break;
	case CGameEvent::onTurn:
		dynamic_cast<CMapObject*> ( mapObject )->onTurn ( event );//change
		break;
	case CGameEvent::onDestroy:
		dynamic_cast<Creatable*> ( mapObject )->onDestroy ( event );
		break;
	case CGameEvent::onCreate:
		dynamic_cast<Creatable*> ( mapObject )->onCreate ( event );
		break;
	case CGameEvent::onUse:
		dynamic_cast<Usable*> ( mapObject )->onUse ( event );
		break;
	}
	delete event;
}


CGameEvent::CGameEvent ( CGameEvent::Type type, CGameObject *cause ) :type ( type ),cause ( cause ) {

}

CGameEvent::Type CGameEvent::getType() const {
	return type;
}
CGameObject *CGameEvent::getCause() const {
	return cause;
}



