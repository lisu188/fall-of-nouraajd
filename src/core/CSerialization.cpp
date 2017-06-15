#include "core/CSerialization.h"
#include "core/CGame.h"
#include "core/CJsonUtil.h"
#include "core/CTypes.h"

std::shared_ptr<CSerializerBase> CSerialization::serializer(
        std::pair<boost::typeindex::type_index, boost::typeindex::type_index> key) {
    return (*CTypes::serializers())[key];
}

void CSerialization::setProperty(std::shared_ptr<CGameObject> object, std::string key, std::shared_ptr<Value> value) {
    switch (value->type()) {
        case nullValue:
            break;
        case booleanValue:
            object->setBoolProperty(key, value->asBool());
            break;
        case intValue:
            object->setNumericProperty(key, value->asInt());
            break;
        case stringValue:
            setStringProperty(object, key, value->asString());
            break;
        case arrayValue:
            setArrayProperty(object, getProperty(object, key), key, value);
            break;
        case objectValue:
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
        auto val = vstd::to_int(value);
        if (val.second) {
            object->setNumericProperty(key, val.first);
        } else if (value == "true") {
            object->setBoolProperty(key, true);
        } else if (value == "false") {
            object->setBoolProperty(key, false);
        } else {
            //TODO: make method that checks if object is JSON
            std::shared_ptr<Value> d = CJsonUtil::from_string(value);
            if (!d || d->isString()) {
                object->setStringProperty(key, value);
            } else {
                setProperty(object, key, d);
            }
        }
    }
}

void CSerialization::setOtherProperty(boost::typeindex::type_index serializedId,
                                      boost::typeindex::type_index deserializedId, std::shared_ptr<CGameObject> object,
                                      std::string key, boost::any value) {
    std::shared_ptr<CSerializerBase> serializer = (*CTypes::serializers())[std::make_pair(serializedId,
                                                                                          deserializedId)];
    boost::any result = vstd::not_null(serializer, "No serializer!")->deserialize(object->getMap(), value);
    if (CTypes::is_pointer_type(result.type())) {
        object->setProperty(key, vstd::any_cast<std::shared_ptr<CGameObject>>(result));
    } else if (CTypes::is_array_type(result.type())) {
        object->setProperty(key, vstd::any_cast<std::set<std::shared_ptr<CGameObject>>>(result));
    } else if (CTypes::is_map_type(result.type())) {
        object->setProperty(key, vstd::any_cast<std::map<std::string, std::shared_ptr<CGameObject>>>(result));
    } else {
        //TODO: primitive properties
        object->setProperty(key, vstd::any_cast<std::set<std::string>>(result));
    }

}

void add_member(std::shared_ptr<Value> object, std::string key, std::string value) {
    (*object)[key] = value;
}

void add_member(std::shared_ptr<Value> object, std::string key, std::shared_ptr<Value> value) {
    (*object)[key] = *value;
}

void add_member(std::shared_ptr<Value> object, std::string key, bool value) {
    (*object)[key] = value;
}

void add_member(std::shared_ptr<Value> object, std::string key, int value) {
    (*object)[key] = value;
}

void add_arr_member(std::shared_ptr<Value> object, std::string value) {
    (*object)[object->size()] = value;
}

void add_arr_member(std::shared_ptr<Value> object, std::shared_ptr<Value> value) {
    (*object)[object->size()] = *value;
}

void add_arr_member(std::shared_ptr<Value> object, bool value) {
    (*object)[object->size()] = value;
}

void add_arr_member(std::shared_ptr<Value> object, int value) {
    (*object)[object->size()] = value;
}

void CSerialization::setProperty(std::shared_ptr<Value> conf, std::string propertyName, boost::any propertyValue) {
    if (propertyValue.type() == boost::typeindex::type_id<int>()) {
        add_member(conf, propertyName, vstd::any_cast<int>(propertyValue));
    } else if (propertyValue.type() == boost::typeindex::type_id<std::string>()) {
        add_member(conf, propertyName, vstd::any_cast<std::string>(propertyValue));
    } else if (propertyValue.type() == boost::typeindex::type_id<bool>()) {
        add_member(conf, propertyName, vstd::any_cast<bool>(propertyValue));
    } else {
        std::shared_ptr<CSerializerBase> serializer;
        for (std::pair<std::pair<boost::typeindex::type_index, boost::typeindex::type_index>, std::shared_ptr<CSerializerBase>> entry:*CTypes::serializers()) {
            auto types = entry.first;
            if (types.second == propertyValue.type()) {
                vstd::fail_if(serializer, "Ambigous serializer!");
                serializer = entry.second;
            }
        }
        add_member(conf, propertyName, vstd::any_cast<std::shared_ptr<Value>>(
                vstd::not_null(serializer, "No serializer!")->serialize(propertyValue)));
    }
}

std::shared_ptr<Value> object_serialize(std::shared_ptr<CGameObject> object) {
    std::shared_ptr<Value> conf = std::make_shared<Value>();
    if (object) {
        add_member(conf, "class", vstd::is_empty(object->getType()) ? object->meta()->name() : object->getType());
        std::shared_ptr<Value> properties = std::make_shared<Value>();
        for (std::shared_ptr<vstd::property> property: object->meta()->properties<CGameObject>(object)) {
            if (property->name() != "name" && property->name() != "type") {
                CSerialization::setProperty(properties, property->name(),
                                            object->getProperty<boost::any>(property->name()));
            }
        }
        add_member(conf, "properties", properties);
    }
    return conf;
}

std::shared_ptr<CGameObject> object_deserialize(std::shared_ptr<CMap> map, std::shared_ptr<Value> config) {
    std::shared_ptr<CGameObject> object;
    if (CJsonUtil::isRef(config)) {
        object = map->getObjectHandler()->createObject(map, (*config)["ref"].asString());
    } else if (CJsonUtil::isType(config)) {
        object = map->getObjectHandler()->getType((*config)["class"].asString());
        if (object) {
            object->setName(vstd::to_hex(object));
            object->setType((*config)["class"].asString());
            object->setMap(map);
        }
    }
    if (object && config->isObject() && config->isMember("properties")) {
        auto properties = &(*config)["properties"];
        for (auto it :properties->getMemberNames()) {
            CSerialization::setProperty(object, it, CJsonUtil::clone(&(*properties)[it]));
        }
    }
    return object;
}

std::shared_ptr<Value> map_serialize(std::map<std::string, std::shared_ptr<CGameObject> > object) {
    std::shared_ptr<Value> ob = std::make_shared<Value>();
    for (std::pair<std::string, std::shared_ptr<CGameObject>> it:object) {
        add_member(ob, it.first,
                   CSerializerFunction<std::shared_ptr<Value>, std::shared_ptr<CGameObject>>::serialize(it.second));
    }
    return ob;
}

std::map<std::string, std::shared_ptr<CGameObject> > map_deserialize(std::shared_ptr<CMap> map,
                                                                     std::shared_ptr<Value> object) {
    std::map<std::string, std::shared_ptr<CGameObject> > ret;
    for (auto it :object->getMemberNames()) {
        ret[it] = CSerializerFunction<std::shared_ptr<Value>, std::shared_ptr<CGameObject>>::deserialize(
                map, CJsonUtil::clone(&(*object)[it]));
    }
    return ret;
}

std::shared_ptr<Value> array_serialize(std::set<std::shared_ptr<CGameObject> > set) {
    std::shared_ptr<Value> arr = std::make_shared<Value>();
    for (std::shared_ptr<CGameObject> ob:set) {
        add_arr_member(arr, CSerializerFunction<std::shared_ptr<Value>, std::shared_ptr<CGameObject>>::serialize(ob));
    }
    return arr;
}

std::set<std::shared_ptr<CGameObject> > array_deserialize(std::shared_ptr<CMap> map,
                                                          std::shared_ptr<Value> object) {
    std::set<std::shared_ptr<CGameObject> > objects;
    for (unsigned int i = 0; i < object->size(); i++) {
        objects.insert(CSerializerFunction<std::shared_ptr<Value>, std::shared_ptr<CGameObject>>::deserialize(map,
                                                                                                              CJsonUtil::clone(
                                                                                                                      &(*object)[i])));
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


std::set<std::shared_ptr<CGameObject> >
CSerializerFunction<std::shared_ptr<Value>, std::set<std::shared_ptr<CGameObject> > >::deserialize(
        std::shared_ptr<CMap> map, std::shared_ptr<Value> object) {
    return array_deserialize(map, object);
}


std::shared_ptr<Value>
CSerializerFunction<std::shared_ptr<Value>, std::map<std::string, std::shared_ptr<CGameObject> > >::serialize(
        std::map<std::string, std::shared_ptr<CGameObject> > object) {
    return map_serialize(object);
}


std::map<std::string, std::shared_ptr<CGameObject> >
CSerializerFunction<std::shared_ptr<Value>, std::map<std::string, std::shared_ptr<CGameObject> > >::deserialize(
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
