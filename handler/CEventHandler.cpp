#include "handler/CHandler.h"
#include "object/CObject.h"
#include "CMap.h"

#include <QMetaEnum>
#include <QDebug>

CEventHandler::CEventHandler ( CMap *map ) :QObject ( map ) {
	this->map=map;
	QMetaEnum typeEnum=CGameEvent::staticMetaObject.enumerator ( CGameEvent::staticMetaObject.indexOfEnumerator ( "Type" ) );
	QJsonArray config=CConfigurationProvider::getConfig ( map->getMapPath()+"/trigger.json" ).toArray();
	for ( auto it=config.begin(); it!=config.end(); it++ ) {
		QJsonObject triggerConfig= ( *it ).toObject();
		QString objectName=triggerConfig["object"].toString();
		QString eventType=triggerConfig["event"].toString();
		QString triggerType=triggerConfig["trigger"].toString();
		CTrigger*trigger=map->getObjectHandler()->createObject<CTrigger*> ( triggerType );
		CGameEvent::Type type=static_cast <CGameEvent::Type> ( typeEnum.keyToValue ( eventType.toStdString().c_str() ) );
		TriggerKey key ( objectName,type );
		if ( triggers.find ( key ) ==triggers.end() ) {
			std::list<CTrigger*> list;
			triggers[key]=list;
		}
		triggers.at ( key ).push_back ( trigger );
	}
}

void CEventHandler::gameEvent (  CGameObject *object ,CGameEvent *event ) const {
	switch ( event->getType() ) {
	case CGameEvent::onEnter:
		dynamic_cast<Visitable*> ( object )->onEnter ( event );
		break;
	case CGameEvent::onLeave:
		dynamic_cast<Visitable*> ( object )->onLeave ( event );
		break;
	case CGameEvent::onTurn:
		dynamic_cast<Turnable*> ( object )->onTurn ( event );
		break;
	case CGameEvent::onDestroy:
		dynamic_cast<Creatable*> ( object )->onDestroy ( event );
		break;
	case CGameEvent::onCreate:
		dynamic_cast<Creatable*> ( object )->onCreate ( event );
		break;
	case CGameEvent::onUse:
		dynamic_cast<Usable*> ( object )->onUse ( event );
		break;
	case CGameEvent::onEquip:
		dynamic_cast<Wearable*> ( object )->onEquip ( event );
		break;
	case CGameEvent::onUnequip:
		dynamic_cast<Wearable*> ( object )->onUnequip (  event );
		break;
	}
	auto it=triggers.find ( TriggerKey ( object->objectName(),event->getType() ) ) ;
	if ( it!=triggers.end() ) {
		std::list<CTrigger*> triggerList= ( *it ).second;
		for ( CTrigger * trigger:triggerList ) {
			trigger->trigger ( object,event );
		}
	}
	delete event;
}


CGameEvent::CGameEvent ( CGameEvent::Type type ) :type ( type ) {

}

CGameEvent::Type CGameEvent::getType() const {
	return type;
}

CGameObject *CGameEventCaused::getCause() const {
	return cause;
}

CGameEventCaused::CGameEventCaused ( CGameEvent::Type type, CGameObject *cause ) :CGameEvent ( type ),cause ( cause ) {

}
