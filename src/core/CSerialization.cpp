#include "core/CSerialization.h"
#include "core/CGame.h"
#include "core/CJsonUtil.h"
#include "core/CTypes.h"

std::shared_ptr<CSerializerBase> CSerialization::serializer(std::pair<int, int> key) {
    return CTypes::serializers()[key];
}

void CSerialization::setProperty(std::shared_ptr<CGameObject> object, std::string key, const Value &value) {
    switch (value.GetType()) {
        case kNullType:
            vstd::fail("Null value detected.");
            break;
        case kTrueType:
        case kFalseType:
            object->setBoolProperty(key, value.GetBool());
            break;
        case kNumberType:
            object->setNumericProperty(key, value.GetInt());
            break;
        case kStringType:
            setStringProperty(object, key, value.GetString());
            break;
        case kArrayType:
            setArrayProperty(object, getProperty(object, key), key, value));
            break;
        case kObjectType:
            setObjectProperty(object, getProperty(object, key), key, value);
            break;
    }
}

QMetaProperty CSerialization::getProperty(std::shared_ptr<CGameObject> object, std::string name) {
    for (int i = 0; i < object->metaObject()->propertyCount(); i++) {
        QMetaProperty property = object->metaObject()->property(i);
        if (name == property.name()) {
            return property;
        }
    }
    return QMetaProperty();
}

void CSerialization::setArrayProperty(std::shared_ptr<CGameObject> object, QMetaProperty property, std::string key,
                                      std::shared_ptr<Value> value) {
    setOtherProperty(qRegisterMetaType<std::shared_ptr<Value>>(),
                     QMetaType::type(property.typeName()) ?
                     QMetaType::type(property.typeName()) :
                     qRegisterMetaType<std::set<std::shared_ptr<CGameObject>>>(),
                     object, key, boost::any
                     ::fromValue(value));
}

void CSerialization::setObjectProperty(std::shared_ptr<CGameObject> object, QMetaProperty property, std::string key,
                                       std::shared_ptr<Value> value) {
    setOtherProperty(qRegisterMetaType<std::shared_ptr<Value>>(),
                     QMetaType::type(property.typeName()) ?
                     QMetaType::type(property.typeName()) :
                     getGenericPropertyType(value),
                     object, key, boost::any
                     ::fromValue(value));
}

void CSerialization::setStringProperty(std::shared_ptr<CGameObject> object, std::string key, std::string value) {
    if (vstd::trim(value) != "") {
        Document d;
        d.Parse(value.c_str());
        if (!d.HasParseError()) {
            bool ok;
            auto val = vstd::to_int(value);
            if (val.second) {
                object->setNumericProperty(key, val.first);
            } else if (value == "true") {
                object->setBoolProperty(key, true);
            } else if (value == "false") {
                object->setBoolProperty(key, false);
            } else {
                object->setStringProperty(key, value);
            }
        } else {
            setProperty(object, key, d);
        }
    }
}

void CSerialization::setOtherProperty(int serializedId, int deserializedId, std::shared_ptr<CGameObject> object,
                                      std::string key, boost::any
                                      value) {
    std::shared_ptr<CSerializerBase> serializer = CTypes::serializers()[std::make_pair(serializedId, deserializedId)];
    value = vstd::not_null(serializer, "No serializer!")->deserialize(object->getMap(), value);
    object->setProperty(key, value);
}

void CSerialization::setProperty(std::shared_ptr<Value> conf, std::string propertyName, boost::any
propertyValue) {
    switch (propertyValue.type()) {
        case boost::any
            ::Int:
            (*conf)[propertyName] = propertyValue.toInt();
            break;
        case boost::any
            ::String:
            (*conf)[propertyName] = propertyValue.toString();
            break;
        case boost::any
            ::Bool:
            (*conf)[propertyName] = propertyValue.toBool();
            break;
        case boost::any
            ::List:
            (*conf)[propertyName] = propertyValue.toJsonArray();
            break;
        case boost::any
            ::Map:
            (*conf)[propertyName] = propertyValue.toJsonObject();
            break;
        default:
            std::shared_ptr<CSerializerBase> serializer;
            for (std::pair<std::pair<int, int>, std::shared_ptr<CSerializerBase>> entry:CTypes::serializers()) {
                std::pair<int, int> types = entry.first;
                int deserialized = types.second;
                if (deserialized == QMetaType::type(propertyValue.typeName())) {
                    vstd::fail_if(serializer, "Ambigous serializer!");
                    serializer = entry.second;
                }
            }
            boost::any
                    result = vstd::not_null(serializer, "No serializer!")->serialize(propertyValue);
            if (result.canConvert(qRegisterMetaType<std::shared_ptr<Value>>())) {
                (*conf)[propertyName] = *result.value<std::shared_ptr<Value>>();
            } else if (result.canConvert(qRegisterMetaType<std::shared_ptr<Value>>())) {
                (*conf)[propertyName] = *result.value<std::shared_ptr<Value>>();
            } else {
                vstd::fail("Not an object or an array");
            }
    }
}

std::shared_ptr<Value> object_serialize(std::shared_ptr<CGameObject> object) {
    std::shared_ptr<Value> conf = std::make_shared<Value>();
    if (object) {
        (*conf)["class"] = object->getType();
        std::shared_ptr<Value> properties = std::make_shared<Value>();
        for (int i = 0; i < object->metaObject()->propertyCount(); i++) {
            QMetaProperty property = object->metaObject()->property(i);
            std::string propertyName = property.name();
            if (propertyName != "objectName" && propertyName != "objectType") {
                boost::any
                        propertyValue = object->property(propertyName);
                CSerialization::setProperty(properties, propertyName, propertyValue);
            }
        }
        for (std::string propertyName:object->dynamicPropertyNames()) {
            CSerialization::setProperty(properties, propertyName, object->property(propertyName));
        }
        (*conf)["properties"] = *properties;
    }
    return conf;
}

std::shared_ptr<CGameObject> object_deserialize(std::shared_ptr<CMap> map, std::shared_ptr<Value> config) {
    std::shared_ptr<CGameObject> object;
    if (!(*config)["ref"].toString().isEmpty()) {
        object = map->getObjectHandler()->createObject(map, (*config)["ref"].toString());
    } else if (!(*config)["class"].toString().isEmpty()) {
        object = map->getObjectHandler()->getType((*config)["class"].toString());
        if (object) {
            object->setName(vstd::to_hex(object));
            object->setType((*config)["class"].toString());
            object->setMap(map);
        }
    }
    if (object) {
        Value properties = (*config)["properties"].toObject();
        for (auto it = properties.begin(); it != properties.end(); it++) {
            CSerialization::setProperty(object, it.key(), it.value());
        }
    }
    return object;
}

std::shared_ptr<Value> map_serialize(std::map<std::string, std::shared_ptr<CGameObject> > object) {
    std::shared_ptr<Value> ob = std::make_shared<Value>();
    for (std::pair<std::string, std::shared_ptr<CGameObject>> it:object) {
        (*ob)[it.first] = *CSerializerFunction<std::shared_ptr<Value>, std::shared_ptr<CGameObject>>::serialize(
                it.second);
    }
    return ob;
}

std::map<std::string, std::shared_ptr<CGameObject> > map_deserialize(std::shared_ptr<CMap> map,
                                                                     std::shared_ptr<Value> object) {
    std::map<std::string, std::shared_ptr<CGameObject> > ret;
    for (auto it = object->begin(); it != object->end(); it++) {
        ret[it.key()] = CSerializerFunction<std::shared_ptr<Value>, std::shared_ptr<CGameObject>>::deserialize(
                map, std::make_shared<Value>(it.value().toObject()));
    }
    return ret;
}

std::shared_ptr<Value> array_serialize(std::set<std::shared_ptr<CGameObject> > set) {
    std::shared_ptr<Value> arr = std::make_shared<Value>();
    for (std::shared_ptr<CGameObject> ob:set) {
        arr->append(*CSerializerFunction<std::shared_ptr<Value>, std::shared_ptr<CGameObject>>::serialize(ob));
    }
    return arr;
}

std::set<std::shared_ptr<CGameObject> > array_deserialize(std::shared_ptr<CMap> map,
                                                          std::shared_ptr<Value> object) {
    std::set<std::shared_ptr<CGameObject> > objects;
    for (Value it:*object) {
        objects.insert(CSerializerFunction<std::shared_ptr<Value>, std::shared_ptr<CGameObject>>::deserialize(map,
                                                                                                              std::make_shared<Value>(
                                                                                                                      it.toObject())));
    }
    return objects;
}


int CSerialization::getGenericPropertyType(std::shared_ptr<Value> object) {
    if (CJsonUtil::isObject(object)) {
        return qRegisterMetaType<std::shared_ptr<CGameObject>>();
    } else if (CJsonUtil::isMap(object)) {
        return qRegisterMetaType<std::map<std::string, std::shared_ptr<CGameObject>>>();
    }
    return vstd::fail<int>("Unable to determine property type!");
}


std::shared_ptr<Value> CSerializerFunction<std::shared_ptr<Value>, std::set<std::shared_ptr<CGameObject> > >::serialize(
        std::set<std::shared_ptr<CGameObject> > set) {
    return array_serialize(set);
}


std::set<std::shared_ptr<CGameObject> > CSerializerFunction<std::shared_ptr<Value>, std::set<std::shared_ptr<CGameObject> > >::deserialize(
        std::shared_ptr<CMap> map, std::shared_ptr<Value> object) {
    return array_deserialize(map, object);
}


std::shared_ptr<Value> CSerializerFunction<std::shared_ptr<Value>, std::map<std::string, std::shared_ptr<CGameObject> > >::serialize(
        std::map<std::string, std::shared_ptr<CGameObject> > object) {
    return map_serialize(object);
}


std::map<std::string, std::shared_ptr<CGameObject> > CSerializerFunction<std::shared_ptr<Value>, std::map<std::string, std::shared_ptr<CGameObject> > >::deserialize(
        std::shared_ptr<CMap> map, std::shared_ptr<Value> object) {
    return map_deserialize(map, object);
}


std::shared_ptr<CGameObject> CSerializerFunction<std::shared_ptr<Value>, std::shared_ptr<CGameObject> >::deserialize(
        std::shared_ptr<CMap> map, std::shared_ptr<Value> config) {
    return object_deserialize(map, config);
}


std::shared_ptr<Value> CSerializerFunction<std::shared_ptr<Value>, std::shared_ptr<CGameObject> >::serialize(
        std::shared_ptr<CGameObject> object) {
    return object_serialize(object);
}
