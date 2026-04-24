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
#pragma once

#include "core/CConcepts.h"
#include "core/CGlobal.h"

class CGame;

class CGameObject;

class CSerializerBase;

class CSerializerBase {
    friend class CSerialization;

  public:
    virtual std::any serialize(std::any object) = 0;

    virtual std::any deserialize(std::shared_ptr<CGame> map, std::any object) = 0;
};

template <typename Serialized, typename Deserialized> class CSerializerFunction {
  public:
    template <typename T = Serialized, typename V = Deserialized>
        requires fn::SharedPtr<V>
    static T serialize(V deserialized) {
        return CSerializerFunction<T, std::shared_ptr<CGameObject>>::serialize(deserialized);
    }

    template <typename T = Serialized, typename V = Deserialized>
        requires fn::SharedPtr<V>
    static V deserialize(std::shared_ptr<CGame> map, T serialized) {
        return std::dynamic_pointer_cast<typename V::element_type>(
            CSerializerFunction<T, std::shared_ptr<CGameObject>>::deserialize(map, serialized));
    }

    template <typename T = Serialized, typename V = Deserialized>
        requires fn::SetLike<V>
    static T serialize(V deserialized) {
        return CSerializerFunction<T, std::set<std::shared_ptr<CGameObject>>>::serialize(
            vstd::cast<std::set<std::shared_ptr<CGameObject>>>(deserialized));
    }

    template <typename T = Serialized, typename V = Deserialized>
        requires fn::SetLike<V>
    static V deserialize(std::shared_ptr<CGame> map, T serialized) {
        return vstd::cast<V>(
            CSerializerFunction<T, std::set<std::shared_ptr<CGameObject>>>::deserialize(map, serialized));
    }

    template <typename T = Serialized, typename V = Deserialized>
        requires fn::MapLike<V>
    static T serialize(V deserialized) {
        return CSerializerFunction<T, std::map<std::string, std::shared_ptr<CGameObject>>>::serialize(
            vstd::cast<std::map<std::string, std::shared_ptr<CGameObject>>>(deserialized));
    }

    template <typename T = Serialized, typename V = Deserialized>
        requires fn::MapLike<V>
    static V deserialize(std::shared_ptr<CGame> map, T serialized) {
        return vstd::cast<V>(
            CSerializerFunction<T, std::map<std::string, std::shared_ptr<CGameObject>>>::deserialize(map, serialized));
    }
};

// inline this functions
extern std::set<std::shared_ptr<CGameObject>> array_deserialize(const std::shared_ptr<CGame> &map,
                                                                const std::shared_ptr<json> &object);

extern std::shared_ptr<json> array_serialize(const std::set<std::shared_ptr<CGameObject>> &set);

extern std::map<std::string, std::shared_ptr<CGameObject>> map_deserialize(const std::shared_ptr<CGame> &map,
                                                                           const std::shared_ptr<json> &object);

extern std::shared_ptr<json> map_serialize(const std::map<std::string, std::shared_ptr<CGameObject>> &object);

extern std::shared_ptr<CGameObject> object_deserialize(const std::shared_ptr<CGame> &game,
                                                       const std::shared_ptr<json> &config);

extern std::shared_ptr<json> object_serialize(const std::shared_ptr<CGameObject> &object);

extern std::set<std::string> array_string_deserialize(std::shared_ptr<CGame> map, std::shared_ptr<json> object);

extern std::shared_ptr<json> array_string_serialize(std::set<std::string> set);

extern void add_member(const std::shared_ptr<json> &object, const std::string &key, const std::string &value);

extern void add_member(const std::shared_ptr<json> &object, const std::string &key, const std::shared_ptr<json> &value);

extern void add_member(const std::shared_ptr<json> &object, const std::string &key, bool value);

extern void add_member(const std::shared_ptr<json> &object, const std::string &key, int value);

extern void add_arr_member(const std::shared_ptr<json> &object, const std::string &value);

extern void add_arr_member(const std::shared_ptr<json> &object, const std::shared_ptr<json> &value);

extern void add_arr_member(const std::shared_ptr<json> &object, bool value);

extern void add_arr_member(const std::shared_ptr<json> &object, int value);

extern std::shared_ptr<CSerializerBase> game_object_pointer_serializer();

extern std::shared_ptr<CSerializerBase> game_object_set_serializer();

extern std::shared_ptr<CSerializerBase> game_object_map_serializer();

template <> class CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>> {
  public:
    static std::shared_ptr<json> serialize(const std::shared_ptr<CGameObject> &object);

    static std::shared_ptr<CGameObject> deserialize(const std::shared_ptr<CGame> &map,
                                                    const std::shared_ptr<json> &config);
};

template <> class CSerializerFunction<std::shared_ptr<json>, std::map<std::string, std::shared_ptr<CGameObject>>> {
  public:
    static std::shared_ptr<json> serialize(const std::map<std::string, std::shared_ptr<CGameObject>> &object);

    static std::map<std::string, std::shared_ptr<CGameObject>> deserialize(const std::shared_ptr<CGame> &map,
                                                                           const std::shared_ptr<json> &object);
};

template <> class CSerializerFunction<std::shared_ptr<json>, std::set<std::shared_ptr<CGameObject>>> {
  public:
    static std::shared_ptr<json> serialize(const std::set<std::shared_ptr<CGameObject>> &set);

    static std::set<std::shared_ptr<CGameObject>> deserialize(const std::shared_ptr<CGame> &map,
                                                              const std::shared_ptr<json> &object);
};

template <typename Serialized, typename Deserialized> class CSerializer : public CSerializerBase {
  public:
    std::any serialize(std::any object) final {
        return std::any(CSerializerFunction<Serialized, Deserialized>::serialize(vstd::any_cast<Deserialized>(object)));
    }

    std::any deserialize(std::shared_ptr<CGame> map, std::any object) final {
        return std::any(
            CSerializerFunction<Serialized, Deserialized>::deserialize(map, vstd::any_cast<Serialized>(object)));
    }
};

template <typename Serialized, typename Deserialized> class CCustomSerializer : public CSerializerBase {
  private:
    std::function<Serialized(Deserialized)> _serialize;
    std::function<Deserialized(std::shared_ptr<CGame>, Serialized)> _deserialize;

  public:
    CCustomSerializer(std::function<Serialized(Deserialized)> _serialize,
                      std::function<Deserialized(std::shared_ptr<CGame>, Serialized)> _deserialize)
        : _serialize(_serialize), _deserialize(_deserialize) {}

    std::any serialize(std::any object) final { return std::any(_serialize(vstd::any_cast<Deserialized>(object))); }

    std::any deserialize(std::shared_ptr<CGame> map, std::any object) final {
        return std::any(_deserialize(map, vstd::any_cast<Serialized>(object)));
    }
};

class CSerialization {
    static std::shared_ptr<CSerializerBase> serializer(std::pair<std::type_index, std::type_index> key);

    template <typename Serialized, typename Deserialized> static std::shared_ptr<CSerializerBase> serializer() {
        return serializer(vstd::type_pair<Serialized, Deserialized>());
    }

  public:
    template <typename Serialized, typename Deserialized> static Serialized serialize(Deserialized deserialized) {
        std::any variant = serializer<Serialized, Deserialized>()->serialize(std::any(deserialized));
        return vstd::any_cast<Serialized>(variant);
    }

    template <typename Serialized, typename Deserialized>
    static Deserialized deserialize(std::shared_ptr<CGame> map, Serialized serialized) {
        std::any variant = serializer<Serialized, Deserialized>()->deserialize(map, std::any(serialized));
        return vstd::any_cast<Deserialized>(variant);
    }

    static void setProperty(const std::shared_ptr<CGameObject> &object, const std::string &key,
                            const std::shared_ptr<json> &value);

    static void setProperty(const std::shared_ptr<json> &conf, const std::string &propertyName,
                            const std::any &propertyValue);

    static std::string generateName(const std::shared_ptr<CGameObject> &object);

  private:
    static std::type_index getProperty(const std::shared_ptr<CGameObject> &object, const std::string &name);

    static std::type_index getGenericPropertyType(const std::shared_ptr<json> &object);

    static void setArrayProperty(const std::shared_ptr<CGameObject> &object, std::type_index property,
                                 const std::string &key, std::shared_ptr<json> value);

    static void setObjectProperty(const std::shared_ptr<CGameObject> &object, std::type_index property,
                                  const std::string &key, std::shared_ptr<json> value);

    static void setStringProperty(const std::shared_ptr<CGameObject> &object, const std::string &key,
                                  const std::string &value);

    static void setNumericProperty(const std::shared_ptr<CGameObject> &object, const std::string &key, int value);

    static void setBooleanProperty(const std::shared_ptr<CGameObject> &object, const std::string &key, bool value);

    static void setOtherProperty(std::type_index serializedId, std::type_index deserializedId,
                                 const std::shared_ptr<CGameObject> &object, const std::string &key,
                                 const std::any &value);

    static bool isString(const std::shared_ptr<CGameObject> &object, const std::string &key);
};
