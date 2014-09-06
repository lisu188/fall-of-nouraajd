#include "CTypeHandler.h"
#include "CMapObject.h"

ATypeHandler *ATypeHandler::getHandler ( QString name ) {
	static  std::list<ATypeHandler*> handlers=CReflection::getInstance()->getInherited<ATypeHandler*>();
	for ( auto it=handlers.begin(); it!=handlers.end(); it++ ) {
		if ( ( *it )->metaObject()->className() ==name ) {
			return *it;
		}
		return NULL;
	}
}

ATypeHandler::ATypeHandler() {}

ATypeHandler::ATypeHandler ( const ATypeHandler & ) {}

CMapObject *ATypeHandler::create ( QString , QJsonObject * ) {return NULL;}

CTypeHandler::CTypeHandler() {}

CTypeHandler::CTypeHandler ( const CTypeHandler & ) {}

CMapObject *CTypeHandler::create ( QString name , QJsonObject *config ) {
	CMapObject *object = NULL;
	int typeId = QMetaType::type ( name.toStdString().c_str() );
	object = ( CMapObject * ) QMetaType::create ( typeId );
	return  object ;
}
