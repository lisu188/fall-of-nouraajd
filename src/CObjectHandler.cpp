#include "CObjectHandler.h"
#include "CConfigurationProvider.h"
#include <QDirIterator>
#include "CMap.h"
#include <QMetaMethod>

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
        setProperty ( object,it.key(),it.value() );
	}
    for ( int i = 0; i < object->metaObject()->propertyCount(); i++ ) {
        QMetaProperty property = object->metaObject()->property ( i );
        if(property.isUser()){
            qDebug()<<property.name()<<":"<<object->property(property.name());
        }
    }
	std::stringstream stream;
	stream << std::hex << (   long ) object;
	QString result ( stream.str().c_str() );
	object->setObjectName ( result );
	object->map=this->map;
	//object->loadFromJson(name);
	object->QObject::setParent ( this );
	return object;
}

void CObjectHandler::setProperty ( QObject *object,QString key, QJsonValue value ) {
	switch ( value.type() ) {
	case QJsonValue::Type::Bool:
        QMetaObject::invokeMethod( object,"setBoolProperty",Q_ARG ( QString, key ),Q_ARG ( bool, value.toBool() ) ) ;
		break;
	case QJsonValue::Type::Double:
        QMetaObject::invokeMethod(  object, "setNumericProperty",Q_ARG ( QString, key ),Q_ARG ( int,value.toInt() ) ) ;
		break;
	case QJsonValue::Type::String:
        QMetaObject::invokeMethod( object,"setStringProperty" ,Q_ARG ( QString, key ),Q_ARG ( QString,value.toString() ) ) ;
		break;
	case QJsonValue::Type::Object:
        QJsonObject propObject=value.toObject();
        QString className=propObject["class"].toString();
        propObject.remove ( "class" );
		int typeId=QMetaType::type ( className.toStdString().c_str() );
        QObject *qObject= ( QObject* ) QMetaType::create ( typeId );
		if ( !qObject ) {
			qFatal ( QString ( "Object "+className+" is null" ).toStdString().c_str() );
		}
        for ( auto it=propObject.begin(); it!=propObject.end(); it++ ) {
			setProperty ( qObject,it.key(),it.value() );
		}
        object->setProperty(key.toStdString().c_str(),QVariant(typeId,qObject));
		break;
	}
}
