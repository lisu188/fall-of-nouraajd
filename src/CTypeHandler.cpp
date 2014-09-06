#include "CTypeHandler.h"
#include "CMapObject.h"

CTypeHandler::CTypeHandler() {}

CTypeHandler::CTypeHandler ( const CTypeHandler & ) {}


MapObject *CTypeHandler::create ( QString name ) {
	//    CMapObject *object = NULL;
	//    QString className = getClassName<T> ( name );
	//    object=this->engine->createObject<CMapObject*> ( className );
	//    if ( object==NULL ) {
	//        int typeId = QMetaType::type ( className.c_str() );
	//        if ( typeId == 0 ) {
	//            return NULL;
	//        }
	//        object = ( CMapObject * ) QMetaType::create ( typeId );
	//    }
	//    QStringstream stream;
	//    stream << std::hex << (   long ) object;
	//    QString result ( stream.str() );
	//    object->name = result;
	//    object->map=this;
	//    object->loadFromJson ( name.toStdString() );
	//    return dynamic_cast<T> ( object );
}

void CTypeHandler::configure ( MapObject *object ) {
}

QJsonObject CTypeHandler::save ( QJsonObject jsonConfig ) {
}

void CTypeHandler::load ( MapObject *object ) {
}
