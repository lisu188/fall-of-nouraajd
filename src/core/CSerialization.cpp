#include "core/CSerialization.h"
#include "core/CGame.h"
#include "core/CJsonUtil.h"
#include "core/CTypes.h"

std::shared_ptr<CSerializerBase> CSerialization::serializer(
        std::pair<boost::typeindex::type_index, boost::typeindex::type_index> key) {
    return CTypes::serializers()[key];
}

void CSerialization::setProperty(std::shared_ptr<CGameObject> object, std::string key, std::shared_ptr<Value> value) {
    switch (value->GetType()) {
        case kNullType:
            vstd::fail("Null value detected.");
            break;
        case kTrueType:
        case kFalseType:
            object->setBoolProperty(key, value->GetBool());
            break;
        case kNumberType:
            object->setNumericProperty(key, value->GetInt());
            break;
        case kStringType:
            setStringProperty(object, key, value->GetString());
            break;
        case kArrayType:
            setArrayProperty(object, getProperty(object, key), key, value);
            break;
        case kObjectType:
            setObjectProperty(object, getProperty(object, key), key, value);
            break;
    }
}

boost::typeindex::type_index CSerialization::getProperty(std::shared_ptr<CGameObject> object, std::string name) {
    return object->meta()->get_property_type(object, name);
}

void CSerialization::setArrayProperty(std::shared_ptr<CGameObject> object, boost::typeindex::type_index property,
                                      std::string key,
                                      std::shared_ptr<Value> value) {
    setOtherProperty(boost::typeindex::type_id<std::shared_ptr<Value>>(),
                     property != V_VOID ?
                     property :
                     boost::typeindex::type_id<std::set<std::shared_ptr<CGameObject>>>(),
                     object, key, boost::any(value));
}

void CSerialization::setObjectProperty(std::shared_ptr<CGameObject> object, boost::typeindex::type_index property,
                                       std::string key,
                                       std::shared_ptr<Value> value) {
    setOtherProperty(boost::typeindex::type_id<std::shared_ptr<Value>>(),
                     property != V_VOID ?
                     property :
                     getGenericPropertyType(value),
                     object, key, boost::any(value));
}

void CSerialization::setStringProperty(std::shared_ptr<CGameObject> object, std::string key, std::string value) {
    if (vstd::trim(value) != "") {
        std::shared_ptr<Value> d = CJsonUtil::from_string(value);
        if (d) {
            setProperty(object, key, d);
        } else {
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
        }
    }
}

void CSerialization::setOtherProperty(boost::typeindex::type_index serializedId,
                                      boost::typeindex::type_index deserializedId, std::shared_ptr<CGameObject> object,
                                      std::string key, boost::any value) {
    std::shared_ptr<CSerializerBase> serializer = CTypes::serializers()[std::make_pair(serializedId, deserializedId)];
    value = vstd::not_null(serializer, "No serializer!")->deserialize(object->getMap(), value);
    object->setProperty(key, value);
}

void CSerialization::setProperty(std::shared_ptr<Value> conf, std::string propertyName, boost::any propertyValue) {
    if (propertyValue.type() == boost::typeindex::type_id<int>()) {
        (*conf)[propertyName.c_str()].SetInt(boost::any_cast<int>(propertyValue));
    } else if (propertyValue.type() == boost::typeindex::type_id<std::string>()) {
        (*conf)[propertyName.c_str()].SetString(boost::any_cast<std::string>(propertyValue).c_str(),
                                                boost::any_cast<std::string>(propertyValue).length());
    } else if (propertyValue.type() == boost::typeindex::type_id<bool>()) {
        (*conf)[propertyName.c_str()].SetBool(boost::any_cast<bool>(propertyValue));
    } else if (false) {
        //TODO: implement list
    }
    if (false) {
        //TODO: implement map
    } else {
        std::shared_ptr<CSerializerBase> serializer;
        for (std::pair<std::pair<boost::typeindex::type_index, boost::typeindex::type_index>, std::shared_ptr<CSerializerBase>> entry:CTypes::serializers()) {
            std::pair<boost::typeindex::type_index, boost::typeindex::type_index> types = entry.first;
            if (types.second == propertyValue.type()) {
                vstd::fail_if(serializer, "Ambigous serializer!");
                serializer = entry.second;
            }
        }
        auto ob = boost::any_cast<std::shared_ptr<Value>>(
                vstd::not_null(serializer, "No serializer!")->serialize(propertyValue));
        for (auto m = ob->MemberBegin(); m != ob->MemberEnd(); m++) {
            //TODO: rewrite object
        }
    }
}

std::shared_ptr<Value> object_serialize(std::shared_ptr<CGameObject> object) {
    std::shared_ptr<Value> conf = std::make_shared<Value>();
    conf->SetObject();
    if (object) {
        (*conf)["class"].SetString(object->getType().c_str(), object->getType().length());
        std::shared_ptr<Value> properties = std::make_shared<Value>();
        for (std::shared_ptr<vstd::property> property: object->meta()->properties<CGameObject>(object)) {
            if (property->name() != "name" && property->name() != "type") {
                CSerialization::setProperty(properties, property->name(),
                                            object->getProperty<boost::any>(property->name()));
            }
        }
        (*conf)["properties"] = *properties;
    }
    return conf;
}

std::shared_ptr<CGameObject> object_deserialize(std::shared_ptr<CMap> map, std::shared_ptr<Value> config) {
    std::shared_ptr<CGameObject> object;
    if (!vstd::is_empty((*config)["ref"].GetString())) {
        object = map->getObjectHandler()->createObject(map, (*config)["ref"].GetString());
    } else if (!vstd::is_empty((*config)["class"].GetString())) {
        object = map->getObjectHandler()->getType((*config)["class"].GetString());
        if (object) {
            object->setName(vstd::to_hex(object));
            object->setType((*config)["class"].GetString());
            object->setMap(map);
        }
    }
    if (object) {
        Value *properties = &(*config)["properties"];
        for (auto it = properties->MemberBegin(); it != properties->MemberEnd(); it++) {
            CSerialization::setProperty(object, it->name.GetString(), CJsonUtil::clone(&it->value));
        }
    }
    return object;
}

std::shared_ptr<Value> map_serialize(std::map<std::string, std::shared_ptr<CGameObject> > object) {
    std::shared_ptr<Value> ob = std::make_shared<Value>();
    ob->SetObject();
    for (std::pair<std::string, std::shared_ptr<CGameObject>> it:object) {
        (*ob)[it.first.c_str()] = *CSerializerFunction<std::shared_ptr<Value>, std::shared_ptr<CGameObject>>::serialize(
                it.second);
    }
    return ob;
}

std::map<std::string, std::shared_ptr<CGameObject> > map_deserialize(std::shared_ptr<CMap> map,
                                                                     std::shared_ptr<Value> object) {
    std::map<std::string, std::shared_ptr<CGameObject> > ret;
    for (auto it = object->MemberBegin(); it != object->MemberEnd(); it++) {
        ret[it->name.GetString()] = CSerializerFunction<std::shared_ptr<Value>, std::shared_ptr<CGameObject>>::deserialize(
                map, CJsonUtil::clone(&it->value));
    }
    return ret;
}

std::shared_ptr<Value> array_serialize(std::set<std::shared_ptr<CGameObject> > set) {
    std::shared_ptr<Value> arr = std::make_shared<Value>();
    arr->SetArray();
    SizeType index = 0;
    for (std::shared_ptr<CGameObject> ob:set) {
        (*arr)[index++] = *CSerializerFunction<std::shared_ptr<Value>, std::shared_ptr<CGameObject>>::serialize(ob);
    }
    return arr;
}

std::set<std::shared_ptr<CGameObject> > array_deserialize(std::shared_ptr<CMap> map,
                                                          std::shared_ptr<Value> object) {
    std::set<std::shared_ptr<CGameObject> > objects;
    for (auto it = object->MemberBegin(); it != object->MemberEnd(); it++) {
        objects.insert(CSerializerFunction<std::shared_ptr<Value>, std::shared_ptr<CGameObject>>::deserialize(map,
                                                                                                              CJsonUtil::clone(
                                                                                                                      &it->value)));
    }
    return objects;
}


boost::typeindex::type_index CSerialization::getGenericPropertyType(std::shared_ptr<Value> object) {
    if (CJsonUtil::isObject(object)) {
        return boost::typeindex::type_id<std::shared_ptr<CGameObject>>();
    } else if (CJsonUtil::isMap(object)) {
        return boost::typeindex::type_id<std::map<std::string, std::shared_ptr<CGameObject>>>();
    }
    vstd::fail("Unable to determine property type!");
    return boost::typeindex::type_index();
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
