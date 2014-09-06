#pragma once
#include <QObject>
#include <QJsonObject>
#include "CTypeHandler.h"
#include "CMapObject.h"
class CMap;
class CObjectHandler : public QObject {
	Q_OBJECT
public:
	CObjectHandler ( CMap *map );
	template<typename T>
	T createMapObject ( QString type ) {
		QJsonObject config=objectConfig[type].toObject();
		QString handlerName=config["handler"].toString();
		QString className=config["class"].toString();
		QJsonObject data=config["data"].toObject();
		ATypeHandler *handler=ATypeHandler::getHandler ( handlerName );
		if ( handler==NULL ) {
			qFatal ( ( "No handler for type: "+type ).toStdString().c_str() );
		}
		CMapObject *object = handler->create ( className,&data );
		if ( object==NULL ) {
			qFatal ( ( "No object for type: "+type ).toStdString().c_str() );
		}
		std::stringstream stream;
		stream << std::hex << (   long ) object;
		QString result ( stream.str().c_str() );
		object->name = result;
		object->map=this->map;
		//object->loadFromJson(name);
		return dynamic_cast<T> ( object );
	}
private:
	CMap *map;
	QJsonObject objectConfig;
};
