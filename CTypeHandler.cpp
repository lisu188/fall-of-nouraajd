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

Constructible *CTypeHandler::create ( QString name ) {
	Constructible *object = nullptr;
	int typeId = QMetaType::type ( name.toStdString().c_str() );
	void *raw=QMetaType::create ( typeId );
	QObject * rawQobject=static_cast<QObject*> ( raw );
	object = dynamic_cast<Constructible*> ( rawQobject );
	return  object ;
}


PyTypeHandler::PyTypeHandler() {

}

PyTypeHandler::PyTypeHandler ( const PyTypeHandler & ) {}

Constructible *PyTypeHandler::create ( QString name ) {
	return CScriptEngine::getInstance()->createObject<Constructible*> ( name );
}


