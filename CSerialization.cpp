#include "CSerialization.h"
#include "CGame.h"
#include "CJsonUtil.h"
#include "CMap.h"

void CSerialization::setProperty ( std::shared_ptr<CGameObject> object, QString key, const QJsonValue &value ) {
    switch ( value.type() ) {
    case QJsonValue::Null:
        fail ( "Null value detected." );
        break;
    case QJsonValue::Undefined:
        fail ( "Undefined value detected." );
        break;
    case QJsonValue::Type::Bool:
        object->setBoolProperty ( key,value.toBool() ) ;
        break;
    case QJsonValue::Type::Double:
        object->setNumericProperty ( key,value.toInt() ) ;
        break;
    case QJsonValue::Type::String:
        setStringProperty ( object, key,value.toString() ) ;
        break;
    case QJsonValue::Type::Array:
        setArrayProperty ( object, getProperty ( object,key ), std::make_shared<QJsonArray> (  value.toArray() ) );
        break;
    case QJsonValue::Type::Object:
        setObjectProperty ( object, getProperty ( object,key ), std::make_shared<QJsonObject> ( value.toObject() ) );
        break;
    }
}

QMetaProperty CSerialization::getProperty ( std::shared_ptr<CGameObject> object, QString name ) {
    for ( int i = 0; i < object->metaObject()->propertyCount(); i++ ) {
        QMetaProperty property = object->metaObject()->property ( i );
        if ( name==property.name() ) {
            return property;
        }
    }
    return QMetaProperty();
}

void CSerialization::setArrayProperty ( std::shared_ptr<CGameObject> object, QMetaProperty property, std::shared_ptr<QJsonArray> prop ) {
    setOtherProperty ( qRegisterMetaType<std::shared_ptr<QJsonArray>>(),
                       QMetaType::type ( property.typeName() ) ?
                       QMetaType::type ( property.typeName() ) :
                       qRegisterMetaType<std::set<std::shared_ptr<CGameObject>>>(),
                       object, property, QVariant::fromValue ( prop ) );
}

void CSerialization::setObjectProperty ( std::shared_ptr<CGameObject> object, QMetaProperty property, std::shared_ptr<QJsonObject> prop ) {
    setOtherProperty ( qRegisterMetaType<std::shared_ptr<QJsonObject>>(),
                       QMetaType::type ( property.typeName() ) ?
                       QMetaType::type ( property.typeName() ) :
                       getGenericPropertyType ( prop ),
                       object, property, QVariant::fromValue ( prop ) );
}

void CSerialization::setStringProperty ( std::shared_ptr<CGameObject> object, QString key, QString value ) {
    if ( value.trimmed() !="" ) {
        QJsonParseError err;
        QJsonDocument doc=QJsonDocument::fromJson ( value.toUtf8(),&err );
        if ( err.error ) {
            bool ok;
            int i=value.toInt ( &ok );
            if ( ok ) {
                object->setNumericProperty ( key,i );
            } else if ( value=="true" ) {
                object->setBoolProperty ( key,true );
            } else if ( value=="false" ) {
                object->setBoolProperty ( key,false );
            } else {
                object->setStringProperty ( key,value );
            }
        } else  {
            setProperty ( object,key, doc.isArray() ?QJsonValue ( doc.array() ) :QJsonValue ( doc.object() ) );
        }
    }
}

void CSerialization::setOtherProperty ( int serializedId, int deserializedId, std::shared_ptr<CGameObject> object, QMetaProperty property, QVariant variant ) {
    std::shared_ptr<CSerializerBase> serializer=CSerializerBase::registry() [std::make_pair ( serializedId,deserializedId )];
    variant=vstd::not_null ( serializer,"No serializer!" )->deserialize ( object->getMap(),variant );
    object->setProperty ( property.name(),variant );
}

void CSerialization::setProperty ( std::shared_ptr<QJsonObject> conf, QString propertyName, QVariant propertyValue ) {
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
        std::shared_ptr<CSerializerBase> serializer;
        for ( std::pair<std::pair<int,int>,std::shared_ptr<CSerializerBase>> entry:CSerializerBase::registry() ) {
            std::pair<int,int> types=entry.first;
            int deserialized=types.second;
            if ( deserialized==QMetaType::type ( propertyValue.typeName() ) ) {
                fail_if ( serializer , "Ambigous serializer!" );
                serializer=entry.second;
            }
        }
        QVariant result=vstd::not_null ( serializer,"No serializer!" )->serialize ( propertyValue );
        if ( result.canConvert ( qRegisterMetaType<std::shared_ptr<QJsonObject>>() ) ) {
            ( *conf ) [propertyName]=*result.value<std::shared_ptr<QJsonObject>>();
        } else if ( result.canConvert ( qRegisterMetaType<std::shared_ptr<QJsonArray>>() ) ) {
            ( *conf ) [propertyName]=*result.value<std::shared_ptr<QJsonArray>>();
        } else {
            fail ( "Not an object or an array" );
        }
    }
}

std::shared_ptr<QJsonObject> object_serialize ( std::shared_ptr<CGameObject> object ) {
    std::shared_ptr<QJsonObject> conf=std::make_shared<QJsonObject>();
    if ( object ) {
        ( *conf ) ["class"]=object->getObjectType();
        std::shared_ptr<QJsonObject> properties=std::make_shared<QJsonObject>();
        for ( int i = 0; i < object->metaObject()->propertyCount(); i++ ) {
            QMetaProperty property = object->metaObject()->property ( i );
            QString propertyName=property.name();
            if ( propertyName!="objectName"&&propertyName!="objectType" ) {
                QVariant propertyValue=object->property ( propertyName );
                CSerialization::setProperty ( properties, propertyName, propertyValue );
            }
        }
        for ( QString propertyName:object->dynamicPropertyNames() ) {
            CSerialization::setProperty ( properties, propertyName, object->property ( propertyName ) );
        }
        ( *conf ) ["properties"]=*properties;
    }
    return conf;
}

std::shared_ptr<CGameObject> object_deserialize ( std::shared_ptr<CMap> map, std::shared_ptr<QJsonObject> config ) {
    std::shared_ptr<CGameObject> object;
    if ( ! ( *config ) ["ref"].toString().isEmpty() ) {
        object=map->getObjectHandler()->createObject ( map, ( *config ) ["ref"].toString() );
    } else if ( ! ( *config ) ["class"].toString().isEmpty() ) {
        object = map->getObjectHandler()->getType ( ( *config ) ["class"].toString() );
        if ( object ) {
            object->setObjectName ( to_hex ( object.get() ) );
            object->setObjectType ( ( *config ) ["class"].toString() );
            object->setMap ( map );
            map->getGame()->addObject ( object );
        }
    }
    if ( object ) {
        QJsonObject properties= ( *config ) ["properties"].toObject();
        for ( auto it=properties.begin(); it!=properties.end(); it++ ) {
            CSerialization::setProperty ( object ,it.key(),it.value() );
        }
        object->setVisible ( false );
    }
    return object;
}

std::shared_ptr<QJsonObject> map_serialize ( std::map<QString, std::shared_ptr<CGameObject> > object ) {
    std::shared_ptr<QJsonObject> ob=std::make_shared<QJsonObject>();
    for ( std::pair<QString, std::shared_ptr<CGameObject>> it:object ) {
        ( *ob ) [it.first]=*CSerializerFunction<std::shared_ptr<QJsonObject>, std::shared_ptr<CGameObject>>::serialize ( it.second );
    }
    return ob;
}

std::map<QString, std::shared_ptr<CGameObject> > map_deserialize ( std::shared_ptr<CMap> map, std::shared_ptr<QJsonObject> object ) {
    std::map<QString, std::shared_ptr<CGameObject> > ret;
    for ( auto it=object->begin(); it!=object->end(); it++ ) {
        ret[it.key()]=CSerializerFunction<std::shared_ptr<QJsonObject>, std::shared_ptr<CGameObject>>::deserialize ( map,std::make_shared<QJsonObject> ( it.value().toObject() ) );
    }
    return ret;
}

std::shared_ptr<QJsonArray> array_serialize ( std::set<std::shared_ptr<CGameObject> > set ) {
    std::shared_ptr<QJsonArray> arr=std::make_shared<QJsonArray>();
    for ( std::shared_ptr<CGameObject> ob:set ) {
        arr->append ( *CSerializerFunction<std::shared_ptr<QJsonObject>, std::shared_ptr<CGameObject>>::serialize ( ob ) );
    }
    return arr;
}

std::set<std::shared_ptr<CGameObject> > array_deserialize ( std::shared_ptr<CMap> map, std::shared_ptr<QJsonArray> object ) {
    std::set<std::shared_ptr<CGameObject> > objects;
    for ( QJsonValue it:*object ) {
        objects.insert ( CSerializerFunction<std::shared_ptr<QJsonObject>, std::shared_ptr<CGameObject>>::deserialize ( map,std::make_shared<QJsonObject> ( it.toObject() ) ) );
    }
    return objects;
}

std::unordered_map<std::pair<int, int>, std::shared_ptr<CSerializerBase> > &CSerializerBase::registry() {
    static std::unordered_map<std::pair<int,int>,std::shared_ptr<CSerializerBase>> reg;
    return reg;
}

int CSerialization::getGenericPropertyType ( std::shared_ptr<QJsonObject> object ) {
    if ( CJsonUtil::isObject ( object ) ) {
        return qRegisterMetaType<std::shared_ptr<CGameObject>>();
    } else if ( CJsonUtil::isMap ( object ) ) {
        return qRegisterMetaType<std::map<QString,std::shared_ptr<CGameObject>>>();
    }
    return fail<int> ( "Unable to determine property type!" );
}


std::shared_ptr<QJsonArray> CSerializerFunction<std::shared_ptr<QJsonArray>, std::set<std::shared_ptr<CGameObject> > >::serialize ( std::set<std::shared_ptr<CGameObject> > set ) {
    return array_serialize ( set );
}


std::set<std::shared_ptr<CGameObject> > CSerializerFunction<std::shared_ptr<QJsonArray>, std::set<std::shared_ptr<CGameObject> > >::deserialize ( std::shared_ptr<CMap> map, std::shared_ptr<QJsonArray> object ) {
    return array_deserialize ( map,object );
}


std::shared_ptr<QJsonObject> CSerializerFunction<std::shared_ptr<QJsonObject>, std::map<QString, std::shared_ptr<CGameObject> > >::serialize ( std::map<QString, std::shared_ptr<CGameObject> > object ) {
    return map_serialize ( object );
}


std::map<QString, std::shared_ptr<CGameObject> > CSerializerFunction<std::shared_ptr<QJsonObject>, std::map<QString, std::shared_ptr<CGameObject> > >::deserialize ( std::shared_ptr<CMap> map, std::shared_ptr<QJsonObject> object ) {
    return map_deserialize ( map,object );
}


std::shared_ptr<CGameObject> CSerializerFunction<std::shared_ptr<QJsonObject>, std::shared_ptr<CGameObject> >::deserialize ( std::shared_ptr<CMap> map, std::shared_ptr<QJsonObject> config ) {
    return object_deserialize ( map,config );
}


std::shared_ptr<QJsonObject> CSerializerFunction<std::shared_ptr<QJsonObject>, std::shared_ptr<CGameObject> >::serialize ( std::shared_ptr<CGameObject> object ) {
    return object_serialize ( object );
}
