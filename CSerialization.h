#pragma once
#include "CGlobal.h"

class CMap;
class CGameObject;
class CSerializerBase;

class CSerializerBase {
    friend class CSerialization;
public:
    virtual QVariant serialize ( QVariant object ) =0;
    virtual QVariant deserialize ( std::shared_ptr<CMap> map,QVariant object ) =0;
protected:
    static std::map<std::pair<int,int>,std::shared_ptr<CSerializerBase>> registry;
};

class CSerialization {
public:
    template <typename Serialized,typename Deserialized>
    static Serialized serialize ( Deserialized deserialized ) {
        QVariant variant=CSerializerBase::registry[std::make_pair ( qRegisterMetaType<Serialized>(),qRegisterMetaType<Deserialized>() )]
                         ->serialize ( QVariant::fromValue ( deserialized ) );
        return variant.value<Serialized>();
    }
    template <typename Serialized,typename Deserialized>
    static Deserialized deserialize ( std::shared_ptr<CMap> map, Serialized serialized ) {
        QVariant variant=CSerializerBase::registry[std::make_pair ( qRegisterMetaType<Serialized>(),qRegisterMetaType<Deserialized>() )]
                         ->deserialize ( map,QVariant::fromValue ( serialized ) );
        return variant.value<Deserialized>();
    }
    static void setProperty ( std::shared_ptr<CGameObject> object , QString key, const QJsonValue &value );
    static void setProperty ( std::shared_ptr<QJsonObject> conf, QString propertyName, QVariant propertyValue );
private:
    static inline QMetaProperty getProperty ( std::shared_ptr<CGameObject> object , QString name );

    template<typename Property>
    static inline void setOtherProperty ( std::shared_ptr<CGameObject> object, QMetaProperty property, Property prop ) {
        _setOtherProperty ( qRegisterMetaType<Property>(), QMetaType::type ( property.typeName() ), object, property, QVariant::fromValue ( prop ) );
    }
    static inline void _setOtherProperty ( int deserializedId, int serializedId, std::shared_ptr<CGameObject> object, QMetaProperty property, QVariant variant );
};

template <typename Serialized,typename Deserialized>
class CSerializerFunction {
public:
    static Serialized serialize ( Deserialized deserialized ) {
        return CSerializerFunction<Serialized,std::shared_ptr<CGameObject>>::serialize ( deserialized );
    }
    static Deserialized deserialize ( std::shared_ptr<CMap> map,Serialized serialized ) {
        return std::dynamic_pointer_cast<typename Deserialized::element_type> ( CSerializerFunction<Serialized,std::shared_ptr<CGameObject>>::deserialize ( map,serialized ) );
    }
};

template<>
class CSerializerFunction<std::shared_ptr<QJsonObject>,std::shared_ptr<CGameObject>> {
public:
    static std::shared_ptr<QJsonObject> serialize ( std::shared_ptr<CGameObject> object );
    static std::shared_ptr<CGameObject> deserialize ( std::shared_ptr<CMap> map, std::shared_ptr<QJsonObject> config );
};

template<>
class CSerializerFunction<std::shared_ptr<QJsonObject>,std::map<QString, std::shared_ptr<CGameObject> >> {
public:
    static std::shared_ptr<QJsonObject> serialize ( std::map<QString, std::shared_ptr<CGameObject> > object );
    static std::map<QString,std::shared_ptr<CGameObject> > deserialize ( std::shared_ptr<CMap> map,std::shared_ptr<QJsonObject> object );
};

template<>
class CSerializerFunction<std::shared_ptr<QJsonArray>,std::set<std::shared_ptr<CGameObject> >> {
public:
    static std::shared_ptr<QJsonArray> serialize ( std::set<std::shared_ptr<CGameObject> > set );
    static std::set<std::shared_ptr<CGameObject> > deserialize ( std::shared_ptr<CMap> map,std::shared_ptr<QJsonArray> object );
};

template <typename Serialized,typename Deserialized>
class CSerializer:public CSerializerBase,public std::enable_shared_from_this<CSerializer<Serialized,Deserialized>> {
public:
    virtual QVariant serialize ( QVariant object ) override final {
        return QVariant::fromValue ( CSerializerFunction<Serialized,Deserialized>::serialize ( object.value<Deserialized>() ) );
    }
    virtual QVariant deserialize ( std::shared_ptr<CMap> map,QVariant object ) override final {
        return QVariant::fromValue ( CSerializerFunction<Serialized,Deserialized>::deserialize ( map,object.value<Serialized>() ) );
    }
    void reg() {
        registry[std::make_pair ( qRegisterMetaType<Serialized>(),qRegisterMetaType<Deserialized>() )]=this->shared_from_this();
    }
};

template<typename Class>
void make_serializable() {
    std::make_shared<CSerializer<std::shared_ptr<QJsonObject>,std::shared_ptr<Class>>>()->reg();
    //std::make_shared<CSerializer<std::shared_ptr<QJsonObject>,std::map<QString, std::shared_ptr<Class>>>>()->reg();
    //std::make_shared<CSerializer<std::shared_ptr<QJsonArray>,std::set<std::shared_ptr<Class>>>>()->reg();
}

Q_DECLARE_METATYPE ( std::shared_ptr<QJsonObject> )
Q_DECLARE_METATYPE ( std::shared_ptr<QJsonArray> )

