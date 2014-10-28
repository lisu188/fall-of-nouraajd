#include "CTypeHandler.h"
#include "CMapObject.h"
#include "CScriptEngine.h"

ATypeHandler *ATypeHandler::getHandler ( QString name ) {
	static  std::list<ATypeHandler*> handlers {new CTypeHandler(),new PyTypeHandler() };
	for ( ATypeHandler* it:handlers ) {
        if ( it->getHandlerName() == name ) {
			return it;
		}
	}
	return nullptr;
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
	return CScriptEngine::getInstance()->createObject<CGameObject*> ( name );
}

QString PyTypeHandler::getHandlerName() {
	return "PyTypeHandler";
}

QString CTypeHandler::getHandlerName() {
	return "CTypeHandler";
}
