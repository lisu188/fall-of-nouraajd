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

CMapObject *ATypeHandler::create ( QString ) {
	return nullptr;
}


CTypeHandler::CTypeHandler() {

}

CTypeHandler::CTypeHandler ( const CTypeHandler & ) {

}

CMapObject *CTypeHandler::create ( QString name ) {
	CMapObject *object = nullptr;
	int typeId = QMetaType::type ( name.toStdString().c_str() );
	object = ( CMapObject * ) QMetaType::create ( typeId );
	return  object ;
}


PyTypeHandler::PyTypeHandler() {

}

PyTypeHandler::PyTypeHandler ( const PyTypeHandler & ) {}

CMapObject *PyTypeHandler::create ( QString name ) {
	return CScriptEngine::getInstance()->createObject<CMapObject*> ( name );
}


