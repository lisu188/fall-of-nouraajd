#pragma once

#include "core/CGlobal.h"


class CMap;

class CGameObject;

class CSerializerBase;

class CSerializerBase {
    friend class CSerialization;

public:
    virtual boost::any
            serialize(boost::any
                      object) = 0;

    virtual boost::any
            deserialize(std::shared_ptr<CMap> map, boost::any
    object) = 0;
};

template<typename Serialized, typename Deserialized>
class CSerializerFunction {
public:
    template<typename T=Serialized, typename V=Deserialized>
    static T serialize(V deserialized, typename std::enable_if<vstd::is_shared_ptr<V>::value>::type * = 0) {
        return CSerializerFunction<T, std::shared_ptr<CGameObject>>::serialize(deserialized);
    }

    template<typename T=Serialized, typename V=Deserialized>
    static V deserialize(std::shared_ptr<CMap> map, T serialized,
                         typename std::enable_if<vstd::is_shared_ptr<V>::value>::type * = 0) {
        return std::dynamic_pointer_cast<typename V::element_type>(
                CSerializerFunction<T, std::shared_ptr<CGameObject>>::deserialize(map, serialized));
    }

    template<typename T=Serialized, typename V=Deserialized>
    static T serialize(V deserialized, typename std::enable_if<vstd::is_set<V>::value>::type * = 0) {
        return CSerializerFunction<T, std::set<std::shared_ptr<CGameObject>>>::serialize(
                vstd::cast<std::set<std::shared_ptr<CGameObject>>>(deserialized));
    }

    template<typename T=Serialized, typename V=Deserialized>
    static V deserialize(std::shared_ptr<CMap> map, T serialized,
                         typename std::enable_if<vstd::is_set<V>::value>::type * = 0) {
        return vstd::cast<V>(
                CSerializerFunction<T, std::set<std::shared_ptr<CGameObject>>>::deserialize(map, serialized));
    }

    template<typename T=Serialized, typename V=Deserialized>
    static T serialize(V deserialized, typename std::enable_if<vstd::is_map<V>::value>::type * = 0) {
        return CSerializerFunction<T, std::map<std::string, std::shared_ptr<CGameObject> >>::serialize(
                vstd::cast<std::map<std::string, std::shared_ptr<CGameObject> >>(deserialized));
    }

    template<typename T=Serialized, typename V=Deserialized>
    static V deserialize(std::shared_ptr<CMap> map, T serialized,
                         typename std::enable_if<vstd::is_map<V>::value>::type * = 0) {
        return vstd::cast<V>(
                CSerializerFunction<T, std::map<std::string, std::shared_ptr<CGameObject> >>::deserialize(map,
                                                                                                          serialized));
    }
};

//inline this functions
extern std::set<std::shared_ptr<CGameObject> > array_deserialize(std::shared_ptr<CMap> map,
                                                                 std::shared_ptr<Value> object);

extern std::shared_ptr<Value> array_serialize(std::set<std::shared_ptr<CGameObject> > set);

extern std::map<std::string, std::shared_ptr<CGameObject> > map_deserialize(std::shared_ptr<CMap> map,
                                                                            std::shared_ptr<Value> object);

extern std::shared_ptr<Value> map_serialize(std::map<std::string, std::shared_ptr<CGameObject> > object);

extern std::shared_ptr<CGameObject> object_deserialize(std::shared_ptr<CMap> map, std::shared_ptr<Value> config);

extern std::shared_ptr<Value> object_serialize(std::shared_ptr<CGameObject> object);

extern std::set<std::string>  array_string_deserialize(std::shared_ptr<CMap> map,
                                                      std::shared_ptr<Value> object);

extern std::shared_ptr<Value>  array_string_serialize(std::set<std::string>  set);

template<>
class CSerializerFunction<std::shared_ptr<Value>, std::shared_ptr<CGameObject>> {
public:
    static std::shared_ptr<Value> serialize(std::shared_ptr<CGameObject> object);

    static std::shared_ptr<CGameObject> deserialize(std::shared_ptr<CMap> map, std::shared_ptr<Value> config);
};

template<>
class CSerializerFunction<std::shared_ptr<Value>, std::map<std::string, std::shared_ptr<CGameObject> >> {
public:
    static std::shared_ptr<Value> serialize(std::map<std::string, std::shared_ptr<CGameObject> > object);

    static std::map<std::string, std::shared_ptr<CGameObject> > deserialize(std::shared_ptr<CMap> map,
                                                                            std::shared_ptr<Value> object);
};

template<>
class CSerializerFunction<std::shared_ptr<Value>, std::set<std::shared_ptr<CGameObject> >> {
public:
    static std::shared_ptr<Value> serialize(std::set<std::shared_ptr<CGameObject> > set);

    static std::set<std::shared_ptr<CGameObject> > deserialize(std::shared_ptr<CMap> map,
                                                               std::shared_ptr<Value> object);
};

template<>
class CSerializerFunction<std::shared_ptr<Value>, std::set<std::string> > {
public:
    static std::shared_ptr<Value> serialize(std::set<std::string> set);

    static std::set<std::string> deserialize(std::shared_ptr<CMap> map,
                                             std::shared_ptr<Value> object);
};


template<typename Serialized, typename Deserialized>
class CSerializer : public CSerializerBase {
public:
    virtual boost::any
    serialize(boost::any
              object) override final {
        return boost::any(
                CSerializerFunction<Serialized, Deserialized>::serialize(vstd::any_cast<Deserialized>(object)));
    }

    virtual boost::any
    deserialize(std::shared_ptr<CMap> map, boost::any
    object) override final {
        return boost::any(
                CSerializerFunction<Serialized, Deserialized>::deserialize(map, vstd::any_cast<Serialized>(object)));
    }
};

//TODO: make std::set<std::string> typedef vstd::tags
template<>
class CSerializer<std::shared_ptr<Json::Value>,std::set<std::string>> : public CSerializerBase {
public:
    virtual boost::any
    serialize(boost::any
              object) override final {
        return boost::any(
                CSerializerFunction<std::shared_ptr<Json::Value>, std::set<std::string>>::serialize(vstd::any_cast<std::set<std::string>>(object)));
    }

    virtual boost::any
    deserialize(std::shared_ptr<CMap> map, boost::any
    object) override final {
        return boost::any(
                CSerializerFunction<std::shared_ptr<Json::Value>, std::set<std::string>>::deserialize(map, vstd::any_cast<std::shared_ptr<Json::Value>>(object)));
    }
};

class CSerialization {
    static std::shared_ptr<CSerializerBase> serializer(
            std::pair<boost::typeindex::type_index, boost::typeindex::type_index> key);

    template<typename Serialized, typename Deserialized>
    static std::shared_ptr<CSerializerBase> serializer() {
        return serializer(vstd::type_pair<Serialized, Deserialized>());
    }

public:
    template<typename Serialized, typename Deserialized>
    static Serialized serialize(Deserialized deserialized) {
        boost::any variant = serializer<Serialized, Deserialized>()
                ->serialize(boost::any(deserialized));
        return vstd::any_cast<Serialized>(variant);
    }

    template<typename Serialized, typename Deserialized>
    static Deserialized deserialize(std::shared_ptr<CMap> map, Serialized serialized) {
        boost::any variant = serializer<Serialized, Deserialized>()
                ->deserialize(map, boost::any(serialized));
        return vstd::any_cast<Deserialized>(variant);
    }

    static void setProperty(std::shared_ptr<CGameObject> object, std::string key, std::shared_ptr<Value> value);

    static void setProperty(std::shared_ptr<Value> conf, std::string propertyName, boost::any
    propertyValue);


private:
    static boost::typeindex::type_index getProperty(std::shared_ptr<CGameObject> object, std::string name);

    static boost::typeindex::type_index getGenericPropertyType(std::shared_ptr<Value> object);

    static void setArrayProperty(std::shared_ptr<CGameObject> object, boost::typeindex::type_index property,
                                 std::string key,
                                 std::shared_ptr<Value> value);

    static void setObjectProperty(std::shared_ptr<CGameObject> object, boost::typeindex::type_index property,
                                  std::string key,
                                  std::shared_ptr<Value> value);

    static void setStringProperty(std::shared_ptr<CGameObject> object, std::string key, std::string value);

    static void setOtherProperty(boost::typeindex::type_index serializedId, boost::typeindex::type_index deserializedId,
                                 std::shared_ptr<CGameObject> object,
                                 std::string key,
                                 boost::any value);
};
