#include "handler/CHandler.h"
#include "object/CObject.h"
#include "CMap.h"

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
    auto range = triggers.equal_range ( TriggerKey ( object->objectName(),event->getType() ) );
    std::for_each (
        range.first,
        range.second,
    [&object,&event] ( TriggerMap::value_type x ) {
        x.second->trigger ( object,event );
    }
    );
    delete event;
}

void CEventHandler::registerTrigger ( QString name, QString type, std::function<CTrigger*() > trigger ) {
    bool ok;
    CGameEvent::Type tp=static_cast<CGameEvent::Type>
                        ( CGameEvent::staticMetaObject.enumerator ( CGameEvent::staticMetaObject.indexOfEnumerator ( "Type" ) )
                          .keyToValue ( type.toStdString().c_str(),&ok ) );
    if ( ok ) {
        triggers.insert ( std::make_pair ( TriggerKey ( name,tp ),trigger() ) ) ;
    } else {
        //handle
    }
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
