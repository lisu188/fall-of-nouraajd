#include "CSerialization.h"
#include "CGame.h"

std::shared_ptr<QJsonObject> CSerialization::serialize ( std::shared_ptr<CGameObject> object ) {
    std::shared_ptr<QJsonObject> conf=std::make_shared<QJsonObject>();
    if ( object ) {
        ( *conf ) ["class"]=object->getObjectType();
        std::shared_ptr<QJsonObject> properties=std::make_shared<QJsonObject>();
        for ( int i = 0; i < object->metaObject()->propertyCount(); i++ ) {
            QMetaProperty property = object->metaObject()->property ( i );
            QString propertyName=property.name();
            if ( propertyName!="objectName"&&propertyName!="objectType" ) {
                QVariant propertyValue=object->property ( propertyName );
                setGenericProperty ( properties, propertyName, propertyValue );
            }
        }
        for ( QString propertyName:object->dynamicPropertyNames() ) {
            setGenericProperty ( properties, propertyName, object->property ( propertyName ) );
        }
        ( *conf ) ["properties"]=*properties;
    }
    return conf;
}

std::shared_ptr<QJsonObject> CSerialization::serialize ( std::map<QString, std::shared_ptr<CGameObject> > object ) {
    std::shared_ptr<QJsonObject> ob=std::make_shared<QJsonObject>();
    for ( std::pair<QString, std::shared_ptr<CGameObject>> it:object ) {
        ( *ob ) [it.first]=*serialize ( it.second );
    }
    return ob;
}

std::shared_ptr<QJsonArray> CSerialization::serialize ( std::set<std::shared_ptr<CGameObject> > set ) {
    std::shared_ptr<QJsonArray> arr=std::make_shared<QJsonArray>();
    for ( std::shared_ptr<CGameObject> ob:set ) {
        arr->append ( *serialize ( ob ) );
    }
    return arr;
}

std::shared_ptr<CGameObject> CSerialization::deserialize ( std::shared_ptr<CMap> map, std::shared_ptr<QJsonObject> config ) {
    std::shared_ptr<CGameObject> object;
    if ( ! ( *config ) ["ref"].toString().isEmpty() ) {
        object=map->getObjectHandler()->createObject ( map, ( *config ) ["ref"].toString() );
    } else if ( ! ( *config ) ["class"].toString().isEmpty() ) {
        object = map->getObjectHandler()->getType ( ( *config ) ["class"].toString() );
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

std::set<std::shared_ptr<CGameObject> > CSerialization::deserialize ( std::shared_ptr<CMap> map, std::shared_ptr<QJsonArray> config ) {
    std::set<std::shared_ptr<CGameObject> > objects;
    for ( QJsonValue it:*config ) {
        objects.insert ( deserialize ( map,std::make_shared<QJsonObject> ( it.toObject() ) ) );
    }
    return objects;
}

std::map<QString, std::shared_ptr<CGameObject> > CSerialization::_deserialize ( std::shared_ptr<CMap> map, std::shared_ptr<QJsonObject> object ) {
    std::map<QString, std::shared_ptr<CGameObject> > ret;
    for ( auto it=object->begin(); it!=object->end(); it++ ) {
        ret[it.key()]=deserialize ( map,std::make_shared<QJsonObject> ( it.value().toObject() ) );
    }
    return ret;
}

void CSerialization::setProperty ( std::shared_ptr<CGameObject> object, QString key, const QJsonValue &value )  {
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

QMetaProperty CSerialization::getProperty ( std::shared_ptr<CGameObject> object, QString name )  {
    for ( int i = 0; i < object->metaObject()->propertyCount(); i++ ) {
        QMetaProperty property = object->metaObject()->property ( i );
        if ( name==property.name() ) {
            return property;
        }
    }
    return QMetaProperty();
}

void CSerialization::setObjectProperty ( std::shared_ptr<CGameObject> object, QMetaProperty property, std::shared_ptr<QJsonObject> propObject ) {
    if ( propObject->size() >0 ) {
        int typeId=QMetaType::type ( property.typeName() );
        //make check based by id
        std::shared_ptr<CGameObject> ob=deserialize ( object->getMap(),propObject );
        if ( ob ) {
            object->setProperty (  property.name(),QVariant ( typeId,&ob ) );
        } else {
            std::map<QString,std::shared_ptr<CGameObject>> map=_deserialize ( object->getMap(),propObject );
            object->setProperty (  property.name(),QVariant ( typeId,&map ) );//remove if not valid
        }
    }
}

void CSerialization::setArrayProperty ( std::shared_ptr<CGameObject> object, QMetaProperty property, std::shared_ptr<QJsonArray> arrayObject ) {
    int typeId=QMetaType::type ( property.typeName() );
    std::set<std::shared_ptr<CGameObject>> arr=deserialize ( object->getMap(),arrayObject );
    object->setProperty (  property.name(),QVariant ( typeId,&arr ) );
}

void CSerialization::setMapProperty ( std::shared_ptr<CGameObject> object, QMetaProperty property, std::shared_ptr<QJsonObject> obj )  {
    int typeId=QMetaType::type ( property.typeName() );
    std::map<QString,std::shared_ptr<CGameObject>> map=_deserialize ( object->getMap(),obj );
    object->setProperty (  property.name(),QVariant ( typeId,&map ) );
}

void CSerialization::setGenericProperty ( std::shared_ptr<QJsonObject> conf, QString propertyName, QVariant propertyValue ) {
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
        if ( QString ( propertyValue.typeName() ) .startsWith ( "std::set" ) ) {
            ( *conf ) [propertyName]=*serialize ( *reinterpret_cast<std::set<std::shared_ptr<CGameObject>>*> ( propertyValue.data() ) );
        } else if ( QString ( propertyValue.typeName() ) .startsWith ( "std::shared_ptr" ) ) {
            ( *conf ) [propertyName]=*serialize (  *reinterpret_cast<std::shared_ptr<CGameObject>*> ( propertyValue.data() ) );
        } else if ( QString ( propertyValue.typeName() ) .endsWith (  "Map" ) ) {
            ( *conf ) [propertyName]=*serialize (  *reinterpret_cast<std::map<QString,std::shared_ptr<CGameObject>>*> ( propertyValue.data() ) );
        }
        break;
    }
}
