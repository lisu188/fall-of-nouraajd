#include "CObjectHandler.h"
#include "CConfigurationProvider.h"
#include <QDirIterator>
#include "CMap.h"

CObjectHandler::CObjectHandler ( CMap *map ) :QObject ( map ) {
	this->map=map;
	QDirIterator dirIt ( "config/objects",QDirIterator::Subdirectories );
	while ( dirIt.hasNext() ) {
		dirIt.next();
		if ( QFileInfo ( dirIt.filePath() ).isFile() )
			if ( QFileInfo ( dirIt.filePath() ).suffix() == "json" ) {
				QString path=dirIt.filePath();
				QJsonObject config=CConfigurationProvider::getConfig ( path ).toObject();
				for ( auto it=config.begin(); it!=config.end(); it++ ) {
					objectConfig[it.key()]=it.value();
				}
			}
	}
}

CMapObject *CObjectHandler::_createMapObject ( QString type ) {
	QJsonObject config=objectConfig[type].toObject();
	QString handlerName=config["handler"].toString();
	QString className=config["class"].toString();
	QJsonObject properties=config["properties"].toObject();
	ATypeHandler *handler=ATypeHandler::getHandler ( handlerName );
	if ( handler==NULL ) {
		qFatal ( ( "No handler for type: "+type ).toStdString().c_str() );
	}
	CMapObject *object = handler->create ( className );
	if ( object==NULL ) {
		qFatal ( ( "No object for type: "+type ).toStdString().c_str() );
	}
	for ( auto it=properties.begin(); it!=properties.end(); it++ ) {
		switch ( it.value().type() ) {
		case QJsonValue::Type::Bool:
			object->setBoolProperty ( it.key(),it.value().toBool() );
			break;
		case QJsonValue::Type::Double:
			object->setNumericProperty ( it.key(),it.value().toInt() );
			break;
		case QJsonValue::Type::String:
			object->setStringProperty ( it.key(),it.value().toString() );
			break;
		}
	}
	std::stringstream stream;
	stream << std::hex << (   long ) object;
	QString result ( stream.str().c_str() );
	object->setObjectName ( result );
	object->map=this->map;
	//object->loadFromJson(name);
	return object;
}
