#pragma once

#include "core/CGlobal.h"
#include "templates/util.h"
#include "templates/cast.h"

class CMap;

class CGameObject;

class CSerializerBase;

class CSerializerBase {
    friend class CSerialization;

public:
    virtual QVariant serialize(QVariant object) = 0;

    virtual QVariant deserialize(std::shared_ptr<CMap> map, QVariant object) = 0;
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
        return CSerializerFunction<T, std::map<QString, std::shared_ptr<CGameObject> >>::serialize(
                vstd::cast<std::map<QString, std::shared_ptr<CGameObject> >>(deserialized));
    }

    template<typename T=Serialized, typename V=Deserialized>
    static V deserialize(std::shared_ptr<CMap> map, T serialized,
                         typename std::enable_if<vstd::is_map<V>::value>::type * = 0) {
        return vstd::cast<V>(
                CSerializerFunction<T, std::map<QString, std::shared_ptr<CGameObject> >>::deserialize(map, serialized));
    }
};

//inline this functions
extern std::set<std::shared_ptr<CGameObject> > array_deserialize(std::shared_ptr<CMap> map,
                                                                 std::shared_ptr<QJsonArray> object);

extern std::shared_ptr<QJsonArray> array_serialize(std::set<std::shared_ptr<CGameObject> > set);

extern std::map<QString, std::shared_ptr<CGameObject> > map_deserialize(std::shared_ptr<CMap> map,
                                                                        std::shared_ptr<QJsonObject> object);

extern std::shared_ptr<QJsonObject> map_serialize(std::map<QString, std::shared_ptr<CGameObject> > object);

extern std::shared_ptr<CGameObject> object_deserialize(std::shared_ptr<CMap> map, std::shared_ptr<QJsonObject> config);

extern std::shared_ptr<QJsonObject> object_serialize(std::shared_ptr<CGameObject> object);

template<>
class CSerializerFunction<std::shared_ptr<QJsonObject>, std::shared_ptr<CGameObject>> {
public:
    static std::shared_ptr<QJsonObject> serialize(std::shared_ptr<CGameObject> object);

    static std::shared_ptr<CGameObject> deserialize(std::shared_ptr<CMap> map, std::shared_ptr<QJsonObject> config);
};

template<>
class CSerializerFunction<std::shared_ptr<QJsonObject>, std::map<QString, std::shared_ptr<CGameObject> >> {
public:
    static std::shared_ptr<QJsonObject> serialize(std::map<QString, std::shared_ptr<CGameObject> > object);

    static std::map<QString, std::shared_ptr<CGameObject> > deserialize(std::shared_ptr<CMap> map,
                                                                        std::shared_ptr<QJsonObject> object);
};

template<>
class CSerializerFunction<std::shared_ptr<QJsonArray>, std::set<std::shared_ptr<CGameObject> >> {
public:
    static std::shared_ptr<QJsonArray> serialize(std::set<std::shared_ptr<CGameObject> > set);

    static std::set<std::shared_ptr<CGameObject> > deserialize(std::shared_ptr<CMap> map,
                                                               std::shared_ptr<QJsonArray> object);
};

template<typename Serialized, typename Deserialized>
class CSerializer : public CSerializerBase {
public:
    virtual QVariant serialize(QVariant object) override final {
        return QVariant::fromValue(
                CSerializerFunction<Serialized, Deserialized>::serialize(object.value<Deserialized>()));
    }

    virtual QVariant deserialize(std::shared_ptr<CMap> map, QVariant object) override final {
        return QVariant::fromValue(
                CSerializerFunction<Serialized, Deserialized>::deserialize(map, object.value<Serialized>()));
    }
};

class CSerialization {
    static std::shared_ptr<CSerializerBase> serializer(std::pair<int, int> key);

    template<typename Serialized, typename Deserialized>
    static std::shared_ptr<CSerializerBase> serializer() {
        return serializer(vstd::type_pair<Serialized, Deserialized>());
    }

public:
    template<typename Serialized, typename Deserialized>
    static Serialized serialize(Deserialized deserialized) {
        QVariant variant = serializer<Serialized, Deserialized>()
                ->serialize(QVariant::fromValue(deserialized));
        return variant.value<Serialized>();
    }

    template<typename Serialized, typename Deserialized>
    static Deserialized deserialize(std::shared_ptr<CMap> map, Serialized serialized) {
        QVariant variant = serializer<Serialized, Deserialized>()
                ->deserialize(map, QVariant::fromValue(serialized));
        return variant.value<Deserialized>();
    }

    static void setProperty(std::shared_ptr<CGameObject> object, QString key, const QJsonValue &value);

    static void setProperty(std::shared_ptr<QJsonObject> conf, QString propertyName, QVariant propertyValue);

private:
    static QMetaProperty getProperty(std::shared_ptr<CGameObject> object, QString name);

    static int getGenericPropertyType(std::shared_ptr<QJsonObject> object);

    static void setArrayProperty(std::shared_ptr<CGameObject> object, QMetaProperty property, QString key,
                                 std::shared_ptr<QJsonArray> value);

    static void setObjectProperty(std::shared_ptr<CGameObject> object, QMetaProperty property, QString key,
                                  std::shared_ptr<QJsonObject> value);

    static void setStringProperty(std::shared_ptr<CGameObject> object, QString key, QString value);

    static void setOtherProperty(int serializedId, int deserializedId, std::shared_ptr<CGameObject> object, QString key,
                                 QVariant value);
};

Q_DECLARE_METATYPE (std::shared_ptr<QJsonObject>)

Q_DECLARE_METATYPE (std::shared_ptr<QJsonArray>)

