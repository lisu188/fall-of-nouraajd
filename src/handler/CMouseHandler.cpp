//#include "CMouseHandler.h"
//#include "object/CGameObject.h"
//#include "core/CMap.h"
//
//CMouseHandler::CMouseHandler() { }
//
//static CClickAction *getClickAction ( CGameObject *parent ) {
//    CClickAction *potentialAction = 0;
//    while ( parent ) {
//        vstd::logger::debug ( parent->metaObject()->className() , "\n" );
//        CClickAction *action = dynamic_cast<CClickAction *> ( parent );
//        if ( action ) {
//            potentialAction = action;
//        }
//        parent = dynamic_cast<CGameObject *> ( parent->parentItem() );
//    }
//    if ( QObject *object = dynamic_cast<QObject *> ( potentialAction ) ) {
//        vstd::logger::debug ( "Delegating click action to ", object->metaObject()->className(), "\n" );
//    }
//    return potentialAction;
//}
//
//void CMouseHandler::handleClick ( std::shared_ptr<CGameObject> object ) {
//    CClickAction *action = getClickAction ( object.get() );
//    if ( action ) {
//        action->onClickAction ( object );
//    }
//}
