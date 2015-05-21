#include "CHandler.h"
#include "provider/CProvider.h"
#include "CMap.h"

CObjectHandler::CObjectHandler ( CObjectHandler *parent ) :parent ( parent ) {

}

void CObjectHandler::logProperties ( CGameObject *object ) const {
    for ( int i = 0; i < object->metaObject()->propertyCount(); i++ ) {
        QMetaProperty property = object->metaObject()->property ( i );
        if ( property.isUser() ) {
            qDebug() <<property.name() <<":"<<object->property ( property.name() );
        }
    }
}

void CObjectHandler::registerConfig ( QString path ) {
    QJsonObject config=CConfigurationProvider::getConfig ( path ).toObject();
    for ( auto it=config.begin(); it!=config.end(); it++ ) {
        objectConfig[it.key()]=it.value();
    }
}

QJsonObject CObjectHandler::getConfig ( QString type ) {
    return objectConfig[type].toObject();
}

std::set<QString> CObjectHandler::getAllTypes() {
    return convert<std::set<QString>> ( objectConfig.keys() );
}

bool CObjectHandler::isFlagSet ( QString type, QString property ) {
    return getConfig ( type ) [property].toBool();
}

CGameObject *CObjectHandler::getType ( QString name ) {
    auto it=constructors.find ( name );
    if ( it !=constructors.end() ) {
        return ( ( *it ).second ) ();
    }
    return nullptr;
}

void CObjectHandler::registerType ( QString name, std::function<CGameObject *() > constructor ) {
    constructors.insert ( std::make_pair ( name,constructor ) );
}

CGameObject *CObjectHandler::_createObject ( CMap *map, QString type ) {
    QJsonObject config=getConfig ( type );
    QString className=config["class"].toString().isEmpty() ? type:config["class"].toString();

    CGameObject *object = getType ( className );
    if ( object==nullptr ) {
        qFatal ( ( "No object for type: "+type ).toStdString().c_str() );
    }
    object->setObjectName ( to_hex ( object ) );
    object->setObjectType ( type );
    object->setMap ( map );

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
