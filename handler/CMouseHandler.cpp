#include "CMouseHandler.h"
#include "object/CGameObject.h"
#include "CMap.h"
#include <QDebug>

CMouseHandler::CMouseHandler ( CMap *map ) :QObject ( map ) {}

void CMouseHandler::handleClick ( CGameObject *object ) {
    CClickAction *action=getClickAction ( object );
    if ( action ) {
        action->onClickAction ( object );
    }
}

CClickAction *CMouseHandler::getClickAction ( CGameObject *object ) {
    CClickAction * potentialAction=nullptr;
    QGraphicsItem *parent=object->toGraphicsItem();
    while ( parent ) {
        CClickAction *  action=dynamic_cast<CClickAction*> ( parent );
        if ( action ) {
            potentialAction=action;
        }
        parent=parent->parentItem();
    }
    if ( QObject *object=dynamic_cast<QObject*> ( potentialAction ) ) {
        qDebug() <<"Delegating click action to "<<object->metaObject()->className() <<"\n";
    }
    return potentialAction;
}
