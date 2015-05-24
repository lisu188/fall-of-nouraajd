#include "handler/CHandler.h"
#include "object/CObject.h"
#include "CMap.h"

void CEventHandler::gameEvent (  std::shared_ptr<CMapObject> object ,std::shared_ptr<CGameEvent> event ) const {
    switch ( event->getType() ) {
    case CGameEvent::onEnter:
        dynamic_cast<Visitable*> ( object.get() )->onEnter ( event );
        break;
    case CGameEvent::onLeave:
        dynamic_cast<Visitable*> ( object.get() )->onLeave ( event );
        break;
    case CGameEvent::onTurn:
        dynamic_cast<Turnable*> ( object.get() )->onTurn ( event );
        break;
    case CGameEvent::onDestroy:
        dynamic_cast<Creatable*> ( object.get() )->onDestroy ( event );
        break;
    case CGameEvent::onCreate:
        dynamic_cast<Creatable*> ( object.get() )->onCreate ( event );
        break;
    case CGameEvent::onUse:
        dynamic_cast<Usable*> ( object.get() )->onUse ( event );
        break;
    case CGameEvent::onEquip:
        dynamic_cast<Wearable*> ( object.get() )->onEquip ( event );
        break;
    case CGameEvent::onUnequip:
        dynamic_cast<Wearable*> ( object.get() )->onUnequip (  event );
        break;
    }
    auto range = triggers.equal_range ( TriggerKey ( object->objectName(),event->getType() ) );
    std::for_each (
        range.first,
        range.second,
    [object,event] ( TriggerMap::value_type x ) {
        x.second->trigger ( object,event );
    }
    );
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

std::shared_ptr<CGameObject> CGameEventCaused::getCause() const {
    return cause;
}

CGameEventCaused::CGameEventCaused ( CGameEvent::Type type, std::shared_ptr<CGameObject> cause ) :CGameEvent ( type ),cause ( cause ) {

}


TriggerKey::TriggerKey ( QString name, CGameEvent::Type type ) :name ( name ),type ( type ) {}

bool TriggerKey::operator== ( const TriggerKey &other ) const {
    return ( type == other.type && name == other.name );
}


std::size_t std::hash<TriggerKey>::operator() ( const TriggerKey &triggerKey ) const {
    using std::size_t;
    int hash=stringHash ( triggerKey.name );
    hash+=static_cast<int> ( triggerKey.type ) *31;
    return hash;
}
