#include "CMouseHandler.h"




void CMouseHandler::handleClick ( CMouseHandler *object ) {
	object->getClickAction()->onClickAction ( object );
}
