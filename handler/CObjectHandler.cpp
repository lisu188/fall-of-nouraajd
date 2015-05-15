#include "CHandler.h"
#include "provider/CProvider.h"
#include <QDirIterator>
#include "CMap.h"
#include <QMetaMethod>
#include <sstream>
#include <QSet>
#include <QString>
#include <QDebug>

CObjectHandler::CObjectHandler ( CMap *map ) :QObject ( map ),map ( map ) {
    auto configFiles=CResourcesProvider::getInstance()->getFiles ( CONFIG );
    configFiles.insert ( map->getMapPath()+"/config.json" );
    for ( auto it=configFiles.begin(); it!=configFiles.end(); it++ ) {
        QJsonObject config=CConfigurationProvider::getConfig ( *it ).toObject();
        for ( auto it=config.begin(); it!=config.end(); it++ ) {
            objectConfig[it.key()]=it.value();
        }
    }
}

void CObjectHandler::logProperties ( CGameObject *object ) const {
    for ( int i = 0; i < object->metaObject()->propertyCount(); i++ ) {
        QMetaProperty property = object->metaObject()->property ( i );
        if ( property.isUser() ) {
            qDebug() <<property.name() <<":"<<object->property ( property.name() );
        }
    }
}

CGameObject *CObjectHandler::_createObject ( QString type ) const {
    QJsonObject config=objectConfig[type].toObject();
    QString className=config["class"].toString().isEmpty() ?type:config["class"].toString();

    CGameObject *object = CTypeHandler::create ( className );
    if ( object==nullptr ) {
        qFatal ( ( "No object for type: "+type ).toStdString().c_str() );
    }

    std::stringstream stream;
    stream << std::hex << ( long ) object;
    QString result ( stream.str().c_str() );
    object->setObjectName ( result );
    object->setObjectType ( type );
    object->setMap ( this->map );

    QJsonObject properties=config["properties"].toObject();
    for ( auto it=properties.begin(); it!=properties.end(); it++ ) {
        setProperty ( object ,it.key(),it.value() );
    }
    object->setVisible ( false );
    //logProperties(object);
    return object;
}

void CObjectHandler::setProperty ( CGameObject *object,QString key, QJsonValue value ) const {
    QByteArray byteArray = key.toUtf8();
    const char* keyName = byteArray.constData();
    switch ( value.type() ) {
    case QJsonValue::Null:
        qFatal ( "Null value detected." );
        break;
    case QJsonValue::Undefined:
        qFatal ( "Undefined value detected." );
        break;
    case QJsonValue::Type::Bool:
        object->setBoolProperty ( key,value.toBool() ) ;
        break;
    case QJsonValue::Type::Double:
        object->setNumericProperty ( key,value.toInt() ) ;
        break;
    case QJsonValue::Type::String:
        object->setStringProperty ( key,value.toString() ) ;
        break;
    case QJsonValue::Type::Array:
        object->setProperty ( keyName,value.toArray().toVariantList() );
        break;
    case QJsonValue::Type::Object:
        QMetaProperty property=getProperty ( object,key );
        QJsonObject propObject=value.toObject();
        if ( !property.isValid() ) {
            object->setProperty ( keyName,propObject.toVariantMap() );
            qDebug() << "Invalid property" <<keyName;
        } else {
            int typeId=QMetaType::type ( property.typeName() );
            if ( typeId==QMetaType::QVariantMap ) {
                object->setProperty ( keyName,propObject.toVariantMap() );
            } else {
                CGameObject *qObject= dynamic_cast<CGameObject*> ( ( QObject* ) QMetaType::create ( typeId ) );
                if ( !qObject ) {
                    qFatal ( QString ( "Object "+QString ( property.typeName() )+" is null" ).toStdString().c_str() );
                }
                qObject->setParent ( object );
                for ( auto it=propObject.begin(); it!=propObject.end(); it++ ) {
                    setProperty ( qObject,it.key(),it.value() );
                }
                object->setProperty ( keyName,QVariant ( typeId,qObject ) );
            }
        }
        break;
    }
}

QMetaProperty CObjectHandler::getProperty ( CGameObject *object, QString name ) const {
    for ( int i = 0; i < object->metaObject()->propertyCount(); i++ ) {
        QMetaProperty property = object->metaObject()->property ( i );
        if ( name==property.name() ) {
            return property;
        }
    }
    return QMetaProperty();
}

const QJsonObject *CObjectHandler::getObjectConfig() const {
    return &objectConfig;
}

CMap *CObjectHandler::getMap() {
    return this->map;
}

