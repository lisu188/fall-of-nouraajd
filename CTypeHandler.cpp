#include "CTypeHandler.h"
#include "CMapObject.h"
#include "CScriptEngine.h"

ATypeHandler *ATypeHandler::getHandler ( QString name ) {
	static  std::list<ATypeHandler*> handlers=CReflection::getInstance()->getInherited<ATypeHandler*>();
	for ( auto it:handlers ) {
		if ( it ->metaObject()->className() ==name ) {
			return it;
		}
	}
	return nullptr;
}

ATypeHandler::ATypeHandler() {

}

ATypeHandler::ATypeHandler ( const ATypeHandler & ) {

}

Constructible *ATypeHandler::create ( QString ) {
	return nullptr;
}


CTypeHandler::CTypeHandler() {

}

CTypeHandler::CTypeHandler ( const CTypeHandler & ) {

}

CGameObject *CTypeHandler::create ( QString name ) {
	CGameObject *object = nullptr;
	int typeId = QMetaType::type ( name.toStdString().c_str() );
	void *raw=QMetaType::create ( typeId );
	CGameObject * rawQobject=static_cast<CGameObject*> ( raw );
	object = dynamic_cast<CGameObject*> ( rawQobject );
	return  object ;
}


PyTypeHandler::PyTypeHandler() {

}

PyTypeHandler::PyTypeHandler ( const PyTypeHandler & ) {}

CGameObject *PyTypeHandler::create ( QString name ) {
	return CScriptEngine::getInstance()->createObject<CGameObject*> ( name );
}


