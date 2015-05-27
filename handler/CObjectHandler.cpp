#include "CHandler.h"
#include "provider/CProvider.h"
#include "CMap.h"
#include "CGame.h"

CObjectHandler::CObjectHandler ( std::shared_ptr<CObjectHandler> parent ) :parent ( parent ) {

}

void CObjectHandler::registerConfig ( QString path ) {
    QJsonObject config=CConfigurationProvider::getConfig ( path ).toObject();
    for ( auto it=config.begin(); it!=config.end(); it++ ) {
        objectConfig[it.key()]=it.value();
    }
}

QJsonObject CObjectHandler::getConfig ( QString type ) {
    if ( !objectConfig[type].isNull() ) {
        return objectConfig[type].toObject();
    } else if ( parent.lock() ) {
        return parent.lock()->getConfig ( type );
    }
    return QJsonObject();
}

std::set<QString> CObjectHandler::getAllTypes() {
    return convert<std::set<QString>> ( objectConfig.keys() );
}

std::shared_ptr<CGameObject> CObjectHandler::getType ( QString name ) {
    if ( ctn ( constructors,name ) ) {
        return std::shared_ptr<CGameObject> ( constructors[name]() );
    } else if ( parent.lock() ) {
        return parent.lock()->getType ( name );
    }
    return std::shared_ptr<CGameObject>();
}

void CObjectHandler::registerType ( QString name,std::function<CGameObject*() >  constructor ) {
    constructors.insert ( std::make_pair ( name,constructor ) );
}

std::shared_ptr<CGameObject> CObjectHandler::buildObject ( QJsonObject &config, std::shared_ptr<CMap> map ) {
    std::shared_ptr<CGameObject> object;
    if ( !config["ref"].toString().isEmpty() ) {
        object=createObject ( map,config["ref"].toString() );
    } else if ( !config["class"].toString().isEmpty() ) {
        object = getType ( config["class"].toString() );
        if ( object ) {
            object->setObjectName ( to_hex ( object.get() ) );
            object->setObjectType (  config["class"].toString() );
            object->setMap ( map );
        }
    }
    if ( object ) {
        QJsonObject properties=config["properties"].toObject();
        for ( auto it=properties.begin(); it!=properties.end(); it++ ) {
            setProperty ( object ,it.key(),it.value() );
        }
        map->getGame()->addObject ( object );
        object->setVisible ( false );
    }
    return object;
}

void CObjectHandler::saveVariantProperty ( std::shared_ptr<QJsonObject> conf, QString propertyName, QVariant propertyValue ) {
    switch ( propertyValue.type() ) {
    case QVariant::Int:
        ( *conf ) ["properties"].toObject() [propertyName]=propertyValue.toInt();
        break;
    case QVariant::String:
        ( *conf ) ["properties"].toObject() [propertyName]=propertyValue.toString();
        break;
    case QVariant::Bool:
        ( *conf ) ["properties"].toObject() [propertyName]=propertyValue.toBool();
        break;
    case QVariant::List:
        ( *conf ) ["properties"].toObject() [propertyName]=propertyValue.toJsonArray();
        break;
    case QVariant::Map:
        ( *conf ) ["properties"].toObject() [propertyName]=propertyValue.toJsonObject();
        break;
    default:
        ( *conf ) ["properties"].toObject() [propertyName]=*serialize ( *reinterpret_cast<std::shared_ptr<CGameObject>*> ( propertyValue.data() ) );
        break;
    }
}

std::shared_ptr<QJsonObject> CObjectHandler::serialize ( std::shared_ptr<CGameObject> object ) {
    std::shared_ptr<QJsonObject> conf=std::make_shared<QJsonObject>();
    ( *conf ) ["class"]=object->getObjectType();
    ( *conf ) ["properties"]=QJsonObject();
    for ( int i = 0; i < object->metaObject()->propertyCount(); i++ ) {
        QMetaProperty property = object->metaObject()->property ( i );
        QString propertyName=property.name();
        QVariant propertyValue=object->property ( propertyName );
        saveVariantProperty ( conf, propertyName, propertyValue );
    }
    for ( QString propertyName:object->dynamicPropertyNames() ) {
        saveVariantProperty ( conf, propertyName, object->property ( propertyName ) );
    }
    return conf;
}

std::shared_ptr<CGameObject> CObjectHandler::deserialize ( std::shared_ptr<CMap> map, std::shared_ptr<QJsonObject> object ) {
    return buildObject ( *object,map );
}

std::shared_ptr<CGameObject> CObjectHandler::_createObject ( std::shared_ptr<CMap> map, QString type ) {
    QJsonObject config=getConfig ( type );
    if ( config.isEmpty() ) {
        config["class"]=type;
    }
    return buildObject ( config, map );
}

void CObjectHandler::setObjectProperty ( std::shared_ptr<CGameObject> object, QMetaProperty property, QJsonObject &propObject, const char* keyName ) {
    int typeId=QMetaType::type ( property.typeName() );
    if ( typeId==QMetaType::QVariantMap ) {
        object->setProperty ( keyName,propObject.toVariantMap() );
    } else {
        std::shared_ptr<CGameObject> ob=buildObject ( propObject,object->getMap() );
        if ( !ob ) {
            qFatal ( QString ( "Object "+QString ( property.typeName() )+" is null" ).toStdString().c_str() );
        }
        object->setProperty ( keyName,QVariant ( typeId,&ob ) );
    }
}

void CObjectHandler::setProperty ( std::shared_ptr<CGameObject> object,QString key, const QJsonValue &value )  {
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
            qDebug() <<"Setting dynamic property:"<<keyName;
        } else {
            qDebug() <<"Setting static property:"<<keyName;
        }
        setObjectProperty ( object, property, propObject, keyName );
        break;
    }
}

QMetaProperty CObjectHandler::getProperty ( std::shared_ptr<CGameObject> object, QString name ) {
    for ( int i = 0; i < object->metaObject()->propertyCount(); i++ ) {
        QMetaProperty property = object->metaObject()->property ( i );
        if ( name==property.name() ) {
            return property;
        }
    }
    return QMetaProperty();
}
