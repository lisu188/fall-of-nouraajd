#include "CHandler.h"
#include "CMapObject.h"
#include "CMap.h"
#include "CScriptEngine.h"

CObjectHandler* ATypeHandler::getObjectHandler(){
    return dynamic_cast<CObjectHandler*>(this->parent());
}

CGameObject *CTypeHandler::create ( QString name ) {
	CGameObject *object = nullptr;
	int typeId = QMetaType::type ( name.toStdString().c_str() );
	void *raw=QMetaType::create ( typeId );
	CGameObject * rawQobject=static_cast<CGameObject*> ( raw );
	object = dynamic_cast<CGameObject*> ( rawQobject );
	return  object ;
}

CGameObject *PyTypeHandler::create ( QString name ) {
    return getObjectHandler()->getMap()->getScriptEngine()->createObject<CGameObject*> ( name );
}

QString PyTypeHandler::getHandlerName() {
	return "PyTypeHandler";
}

QString CTypeHandler::getHandlerName() {
	return "CTypeHandler";
}
