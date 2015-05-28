#include "CHandler.h"
#include "provider/CProvider.h"
#include "CMap.h"
#include "CGame.h"

CObjectHandler::CObjectHandler ( std::shared_ptr<CObjectHandler> parent ) :parent ( parent ) {

}

void CObjectHandler::registerConfig ( QString path ) {
    std::shared_ptr<QJsonObject> config=CConfigurationProvider::getConfig ( path );
    for ( auto it=config->begin(); it!=config->end(); it++ ) {
        objectConfig[it.key()]=std::make_shared<QJsonObject> ( it.value().toObject() );
    }
}

std::shared_ptr<QJsonObject> CObjectHandler::getConfig ( QString type ) {
    if ( ctn ( objectConfig,type ) ) {
        return objectConfig[type];
    } else if ( parent.lock() ) {
        return parent.lock()->getConfig ( type );
    }
    return std::make_shared<QJsonObject>();
}

std::set<QString> CObjectHandler::getAllTypes() {
    return *reinterpret_cast<std::set<QString>*> ( 0 ); //return convert<std::set<QString>> ( objectConfig.keys() );
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

std::shared_ptr<CGameObject> CObjectHandler::buildObject ( std::shared_ptr<CMap> map , std::shared_ptr<QJsonObject> config ) {
    std::shared_ptr<CGameObject> object;
    if ( ! ( *config ) ["ref"].toString().isEmpty() ) {
        object=createObject ( map, ( *config ) ["ref"].toString() );
    } else if ( ! ( *config ) ["class"].toString().isEmpty() ) {
        object = getType ( ( *config ) ["class"].toString() );
        if ( object ) {
            object->setObjectName ( to_hex ( object.get() ) );
            object->setObjectType (  ( *config ) ["class"].toString() );
            object->setMap ( map );
        }
    }
    if ( object ) {
        QJsonObject properties= ( *config ) ["properties"].toObject();
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
        ( *conf ) [propertyName]=propertyValue.toInt();
        break;
    case QVariant::String:
        ( *conf ) [propertyName]=propertyValue.toString();
        break;
    case QVariant::Bool:
        ( *conf ) [propertyName]=propertyValue.toBool();
        break;
    case QVariant::List:
        ( *conf ) [propertyName]=propertyValue.toJsonArray();
        break;
    case QVariant::Map:
        ( *conf ) [propertyName]=propertyValue.toJsonObject();
        break;
    default:
        ( *conf ) [propertyName]=*serialize ( *reinterpret_cast<std::shared_ptr<CGameObject>*> ( propertyValue.data() ) );
        break;
    }
}

std::shared_ptr<QJsonObject> CObjectHandler::serialize ( std::shared_ptr<CGameObject> object ) {
    std::shared_ptr<QJsonObject> conf=std::make_shared<QJsonObject>();
    ( *conf ) ["class"]=object->getObjectType();
    std::shared_ptr<QJsonObject> properties=std::make_shared<QJsonObject>();
    for ( int i = 0; i < object->metaObject()->propertyCount(); i++ ) {
        QMetaProperty property = object->metaObject()->property ( i );
        QString propertyName=property.name();
        if ( propertyName!="objectName"&&propertyName!="objectType" ) {
            QVariant propertyValue=object->property ( propertyName );
            saveVariantProperty ( properties, propertyName, propertyValue );
        }
    }
    for ( QString propertyName:object->dynamicPropertyNames() ) {
        saveVariantProperty ( properties, propertyName, object->property ( propertyName ) );
    }
    ( *conf ) ["properties"]=*properties;
    return conf;
}

std::shared_ptr<CGameObject> CObjectHandler::deserialize ( std::shared_ptr<CMap> map, std::shared_ptr<QJsonObject> object ) {
    return buildObject ( map,object );
}

std::shared_ptr<CGameObject> CObjectHandler::_createObject ( std::shared_ptr<CMap> map, QString type ) {
    std::shared_ptr<QJsonObject> config=getConfig ( type );
    if ( ( *config ).isEmpty() ) {
        ( *config ) ["class"]=type;
    }
    return buildObject ( map,config );
}

void CObjectHandler::setObjectProperty ( std::shared_ptr<CGameObject> object, QMetaProperty property, std::shared_ptr<QJsonObject> propObject ) {
    int typeId=QMetaType::type ( property.typeName() );
    if ( typeId==QMetaType::QVariantMap ) {
        object->setProperty ( property.name(),propObject->toVariantMap() );
    } else {
        std::shared_ptr<CGameObject> ob=buildObject ( object->getMap(),propObject );
        if ( !ob ) {
            qFatal ( QString ( "Object "+QString ( property.typeName() )+" is null" ).toStdString().c_str() );
        }
        object->setProperty (  property.name(),QVariant ( typeId,&ob ) );
    }
}

void CObjectHandler::setArrayProperty ( std::shared_ptr<CGameObject> object, QMetaProperty property, std::shared_ptr<QJsonArray> arrayObject ) {
    int typeId=QMetaType::type ( property.typeName() );
    if ( typeId==QMetaType::QVariantList ) {
        object->setProperty ( property.name(),arrayObject->toVariantList() );
    } else {
        std::set<std::shared_ptr<CGameObject>> arr;
        for ( QJsonValue val:*arrayObject ) {
            std::shared_ptr<CGameObject> ob=buildObject ( object->getMap(),std::make_shared<QJsonObject> ( val.toObject() ) );
            if ( !ob ) {
                qFatal ( QString ( "Object "+QString ( property.typeName() )+" is null" ).toStdString().c_str() );
            }
            arr.insert ( ob );
        }
        object->setProperty (  property.name(),QVariant ( typeId,&arr ) );
    }
}

void CObjectHandler::setProperty ( std::shared_ptr<CGameObject> object,QString key, const QJsonValue &value )  {
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
        setArrayProperty ( object, getProperty ( object,key ), std::make_shared<QJsonArray> ( value.toArray() ) );
        break;
    case QJsonValue::Type::Object:
        setObjectProperty ( object, getProperty ( object,key ), std::make_shared<QJsonObject> ( value.toObject() ) );
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
