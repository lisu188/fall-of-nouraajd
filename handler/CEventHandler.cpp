#include "handler/CHandler.h"
#include "object/CObject.h"
#include "CUtil.h"
#include "CMap.h"

void CEventHandler::gameEvent (  std::shared_ptr<CMapObject> object ,std::shared_ptr<CGameEvent> event ) const {
    switch ( event->getType() ) {
    case CGameEvent::onEnter:
        cast<Visitable > ( object )->onEnter ( event );
        break;
    case CGameEvent::onLeave:
        cast<Visitable > ( object )->onLeave ( event );
        break;
    case CGameEvent::onTurn:
        cast<Turnable > ( object )->onTurn ( event );
        break;
    case CGameEvent::onDestroy:
        cast<Creatable > ( object )->onDestroy ( event );
        break;
    case CGameEvent::onCreate:
        cast<Creatable > ( object )->onCreate ( event );
        break;
    case CGameEvent::onUse:
        cast<Usable > ( object )->onUse ( event );
        break;
    case CGameEvent::onEquip:
        cast<Wearable > ( object )->onEquip ( event );
        break;
    case CGameEvent::onUnequip:
        cast<Wearable > ( object )->onUnequip (  event );
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

void CEventHandler::registerTrigger ( QString name, QString type,  std::function<CTrigger*() >trigger ) {
    bool ok;
    CGameEvent::Type tp=static_cast<CGameEvent::Type>
                        ( CGameEvent::staticMetaObject.enumerator ( CGameEvent::staticMetaObject.indexOfEnumerator ( "Type" ) )
                          .keyToValue ( type.toStdString().c_str(),&ok ) );
    if ( ok ) {
        triggers.insert ( std::make_pair ( TriggerKey ( name,tp ),std::shared_ptr<CTrigger>(trigger()) ) ) ;
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
    hash+=static_cast<int> ( triggerKey.type ) * 31;
    return hash;
}
