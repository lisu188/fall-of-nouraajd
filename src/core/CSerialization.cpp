/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025  Andrzej Lis

This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
#include "core/CSerialization.h"
#include "core/CGame.h"
#include "core/CJsonUtil.h"
#include "core/CTypes.h"

std::shared_ptr<CSerializerBase> CSerialization::serializer(
    std::pair<boost::typeindex::type_index, boost::typeindex::type_index> key) {
  return (*CTypes::serializers())[key];
}

void CSerialization::setProperty(const std::shared_ptr<CGameObject> &object,
                                 const std::string &key,
                                 const std::shared_ptr<json> &value) {
  if (value->is_boolean()) {
    setBooleanProperty(object, key, value->get<bool>());
  } else if (value->is_number()) {
    setNumericProperty(object, key, value->get<int>());
  } else if (value->is_string()) {
    setStringProperty(object, key, value->get<std::string>());
  } else if (value->is_array()) {
    setArrayProperty(object, getProperty(object, key), key, value);
  } else if (value->is_object()) {
    setObjectProperty(object, getProperty(object, key), key, value);
  }
}

boost::typeindex::type_index
CSerialization::getProperty(const std::shared_ptr<CGameObject> &object,
                            const std::string &name) {
  return object->meta()->get_property_type(object, name);
}

void CSerialization::setArrayProperty(
    const std::shared_ptr<CGameObject> &object,
    boost::typeindex::type_index property, const std::string &key,
    std::shared_ptr<json> value) {
  setOtherProperty(
      boost::typeindex::type_id<std::shared_ptr<json>>(),
      property != V_VOID
          ? property
          : boost::typeindex::type_id<std::set<std::shared_ptr<CGameObject>>>(),
      object, key, boost::any(value));
}

void CSerialization::setObjectProperty(
    const std::shared_ptr<CGameObject> &object,
    boost::typeindex::type_index property, const std::string &key,
    std::shared_ptr<json> value) {
  setOtherProperty(boost::typeindex::type_id<std::shared_ptr<json>>(),
                   property != V_VOID ? property
                                      : getGenericPropertyType(value),
                   object, key, boost::any(value));
}

void CSerialization::setNumericProperty(
    const std::shared_ptr<CGameObject> &object, const std::string &key,
    int value) {
  if (isString(object, key)) {
    object->setStringProperty(key, vstd::str(value));
  } else {
    object->setNumericProperty(key, value);
  }
}

void CSerialization::setBooleanProperty(
    const std::shared_ptr<CGameObject> &object, const std::string &key,
    bool value) {
  if (isString(object, key)) {
    object->setStringProperty(key, vstd::str(value));
  } else {
    object->setBoolProperty(key, value);
  }
}

void CSerialization::setStringProperty(
    const std::shared_ptr<CGameObject> &object, const std::string &key,
    const std::string &value) {
  if (!vstd::trim(value).empty()) {
    auto val = vstd::to_int(value);
    if (val.second) {
      setNumericProperty(object, key, val.first);
    } else if (value == "true") {
      setBooleanProperty(object, key, true);
    } else if (value == "false") {
      setBooleanProperty(object, key, false);
    } else {
      // TODO: make method that checks if object is JSON
      std::shared_ptr<json> d = CJsonUtil::from_string(value);
      if (d && d->is_number() && vstd::str(d->get<double>()) != value) {
        object->setStringProperty(key, value);
      } else if (!d || d->is_string()) {
        object->setStringProperty(key, value);
      } else {
        setProperty(object, key, d);
      }
    }
  }
}

bool CSerialization::isString(const std::shared_ptr<CGameObject> &object,
                              const std::string &key) {
  return getProperty(object, key) == boost::typeindex::type_id<std::string>();
}

void CSerialization::setOtherProperty(
    boost::typeindex::type_index serializedId,
    boost::typeindex::type_index deserializedId,
    const std::shared_ptr<CGameObject> &object, const std::string &key,
    const boost::any &value) {
  std::shared_ptr<CSerializerBase> serializer =
      (*CTypes::serializers())[std::make_pair(serializedId, deserializedId)];
  boost::any result = vstd::not_null(serializer, "No serializer!")
                          ->deserialize(object->getGame(), value);
  if (CTypes::is_pointer_type(result.type())) {
    object->setProperty(key,
                        vstd::any_cast<std::shared_ptr<CGameObject>>(result));
  } else if (CTypes::is_array_type(result.type())) {
    object->setProperty(
        key, vstd::any_cast<std::set<std::shared_ptr<CGameObject>>>(result));
  } else if (CTypes::is_map_type(result.type())) {
    object->setProperty(
        key,
        vstd::any_cast<std::map<std::string, std::shared_ptr<CGameObject>>>(
            result));
  } else {
    CTypes::set_custom_property(object, key, result);
  }
}

void add_member(const std::shared_ptr<json> &object, const std::string &key,
                const std::string &value) {
  (*object)[key] = value;
}

void add_member(const std::shared_ptr<json> &object, const std::string &key,
                const std::shared_ptr<json> &value) {
  (*object)[key] = *value;
}

void add_member(const std::shared_ptr<json> &object, const std::string &key,
                bool value) {
  (*object)[key] = value;
}

void add_member(const std::shared_ptr<json> &object, const std::string &key,
                int value) {
  (*object)[key] = value;
}

void add_arr_member(const std::shared_ptr<json> &object,
                    const std::string &value) {
  (*object)[object->size()] = value;
}

void add_arr_member(const std::shared_ptr<json> &object,
                    const std::shared_ptr<json> &value) {
  (*object)[object->size()] = *value;
}

void add_arr_member(const std::shared_ptr<json> &object, bool value) {
  (*object)[object->size()] = value;
}

void add_arr_member(const std::shared_ptr<json> &object, int value) {
  (*object)[object->size()] = value;
}

void CSerialization::setProperty(const std::shared_ptr<json> &conf,
                                 const std::string &propertyName,
                                 const boost::any &propertyValue) {
  if (propertyValue.type() == boost::typeindex::type_id<int>()) {
    add_member(conf, propertyName, vstd::any_cast<int>(propertyValue));
  } else if (propertyValue.type() == boost::typeindex::type_id<std::string>()) {
    add_member(conf, propertyName, vstd::any_cast<std::string>(propertyValue));
  } else if (propertyValue.type() == boost::typeindex::type_id<bool>()) {
    add_member(conf, propertyName, vstd::any_cast<bool>(propertyValue));
  } else {
    std::shared_ptr<CSerializerBase> serializer;
    for (const auto &entry : *CTypes::serializers()) {
      auto types = entry.first;
      if (types.second == propertyValue.type()) {
        vstd::fail_if(serializer, "Ambiguous serializer!");
        serializer = entry.second;
      }
    }
    if (serializer) {
      add_member(conf, propertyName,
                 vstd::any_cast<std::shared_ptr<json>>(
                     serializer->serialize(propertyValue)));
    } else {
      vstd::logger::warning("No serializer for:", propertyName);
    }
  }
}

std::shared_ptr<json>
object_serialize(const std::shared_ptr<CGameObject> &object) {
  std::shared_ptr<json> conf = std::make_shared<json>();
  if (object) {
    add_member(conf, "class",
               vstd::is_empty(object->getType()) ? object->meta()->name()
                                                 : object->getType());
    std::shared_ptr<json> properties = std::make_shared<json>();
    object->meta()->for_all_properties(object, [&](auto property) {
      if (property->name() != "type") {
        CSerialization::setProperty(
            properties, property->name(),
            object->getProperty<boost::any>(property->name()));
      }
    });
    add_member(conf, "properties", properties);
  }
  return conf;
}

std::shared_ptr<CGameObject>
object_deserialize(const std::shared_ptr<CGame> &game,
                   const std::shared_ptr<json> &config) {
  std::shared_ptr<CGameObject> object;
  if (CJsonUtil::isRef(config)) {
    object = game->getObjectHandler()->createObject(
        game, (*config)["ref"].get<std::string>());
  } else if (CJsonUtil::isType(config)) {
    object = game->getObjectHandler()->getType(
        (*config)["class"].get<std::string>());
    if (object) {
      if (vstd::is_empty(object->getName())) {
        object->setName(CSerialization::generateName(object));
      }
      object->setType((*config)["class"].get<std::string>());
      object->setGame(game);
    }
  }
  if (object && config->is_object() && config->count("properties")) {
    auto properties = &(*config)["properties"];
    for (auto [key, value] : properties->items()) {
      CSerialization::setProperty(object, key, CJsonUtil::clone(value));
    }
  }
  if (object) {
    object->meta()->invoke_method<void>("initialize", object);
  }
  return object;
}

// TODO: handle collisions
std::string
CSerialization::generateName(const std::shared_ptr<CGameObject> &object) {
  return vstd::to_hex_hash(to_hex(object), vstd::rand());
}

std::shared_ptr<json> map_serialize(
    const std::map<std::string, std::shared_ptr<CGameObject>> &object) {
  std::shared_ptr<json> ob = std::make_shared<json>();
  for (const auto &it : object) {
    add_member(ob, it.first,
               CSerializerFunction<
                   std::shared_ptr<json>,
                   std::shared_ptr<CGameObject>>::serialize(it.second));
  }
  return ob;
}

std::map<std::string, std::shared_ptr<CGameObject>>
map_deserialize(const std::shared_ptr<CGame> &map,
                const std::shared_ptr<json> &object) {
  std::map<std::string, std::shared_ptr<CGameObject>> ret;
  for (auto [key, val] : object->items()) {
    ret[key] = CSerializerFunction<
        std::shared_ptr<json>,
        std::shared_ptr<CGameObject>>::deserialize(map, CJsonUtil::clone(val));
  }
  return ret;
}

std::shared_ptr<json>
array_serialize(const std::set<std::shared_ptr<CGameObject>> &set) {
  std::shared_ptr<json> arr = std::make_shared<json>();
  for (const auto &ob : set) {
    add_arr_member(
        arr, CSerializerFunction<std::shared_ptr<json>,
                                 std::shared_ptr<CGameObject>>::serialize(ob));
  }
  return arr;
}

std::set<std::shared_ptr<CGameObject>>
array_deserialize(const std::shared_ptr<CGame> &map,
                  const std::shared_ptr<json> &object) {
  std::set<std::shared_ptr<CGameObject>> objects;
  for (unsigned int i = 0; i < object->size(); i++) {
    objects.insert(CSerializerFunction<std::shared_ptr<json>,
                                       std::shared_ptr<CGameObject>>::
                       deserialize(map, CJsonUtil::clone(&(*object)[i])));
  }
  return objects;
}

boost::typeindex::type_index
CSerialization::getGenericPropertyType(const std::shared_ptr<json> &object) {
  if (CJsonUtil::isObject(object)) {
    return boost::typeindex::type_id<std::shared_ptr<CGameObject>>();
  } else if (CJsonUtil::isMap(object)) {
    return boost::typeindex::type_id<
        std::map<std::string, std::shared_ptr<CGameObject>>>();
  }
  vstd::fail("Unable to determine property type!");
  return boost::typeindex::type_index();
}

std::shared_ptr<json>
CSerializerFunction<std::shared_ptr<json>,
                    std::set<std::shared_ptr<CGameObject>>>::
    serialize(const std::set<std::shared_ptr<CGameObject>> &set) {
  return array_serialize(set);
}

std::set<std::shared_ptr<CGameObject>>
CSerializerFunction<std::shared_ptr<json>,
                    std::set<std::shared_ptr<CGameObject>>>::
    deserialize(const std::shared_ptr<CGame> &map,
                const std::shared_ptr<json> &object) {
  return array_deserialize(map, object);
}

std::shared_ptr<json>
CSerializerFunction<std::shared_ptr<json>,
                    std::map<std::string, std::shared_ptr<CGameObject>>>::
    serialize(
        const std::map<std::string, std::shared_ptr<CGameObject>> &object) {
  return map_serialize(object);
}

std::map<std::string, std::shared_ptr<CGameObject>>
CSerializerFunction<std::shared_ptr<json>,
                    std::map<std::string, std::shared_ptr<CGameObject>>>::
    deserialize(const std::shared_ptr<CGame> &map,
                const std::shared_ptr<json> &object) {
  return map_deserialize(map, object);
}

std::shared_ptr<CGameObject>
CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::
    deserialize(const std::shared_ptr<CGame> &map,
                const std::shared_ptr<json> &config) {
  return object_deserialize(map, config);
}

std::shared_ptr<json>
CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::
    serialize(const std::shared_ptr<CGameObject> &object) {
  return object_serialize(object);
}
