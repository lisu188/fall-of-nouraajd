#include "CMouseHandler.h"
#include "object/CGameObject.h"
#include "CMap.h"
#include <QDebug>

CMouseHandler::CMouseHandler (  )  {}

static inline CClickAction* getClickAction ( CGameObject* parent ) {
    CClickAction* potentialAction=0;
    while ( parent ) {
        qDebug() <<parent->metaObject()->className() <<"\n";
        CClickAction* action=dynamic_cast<CClickAction*> ( parent );
        if ( action ) {
            potentialAction=action;
        }
        parent=dynamic_cast<CGameObject*> ( parent->parentItem() );
    }
    if (   QObject* object=dynamic_cast<QObject*> ( potentialAction ) ) {
        qDebug() <<"Delegating click action to "<<object->metaObject()->className() <<"\n";
    }
    return potentialAction;
}
void CMouseHandler::handleClick ( std::shared_ptr<CGameObject> object ) {
    CClickAction* action=getClickAction ( object.get() );
    if ( action ) {
        action->onClickAction ( object );
    }
}
