#pragma once
#include "CGlobal.h"
#include "CUtil.h"
#include "CCast.h"

class CMap;
class CGameObject;
class CSerializerBase;

class CSerializerBase {
    friend class CSerialization;
public:
    virtual QVariant serialize ( QVariant object ) =0;
    virtual QVariant deserialize ( std::shared_ptr<CMap> map,QVariant object ) =0;
protected:
    static std::unordered_map<std::pair<int,int>,std::shared_ptr<CSerializerBase>>& registry();
};

template <typename Serialized,typename Deserialized>
class CSerializerFunction  {
public:
    template<typename T=Serialized,typename V=Deserialized>
    static T serialize ( V deserialized,typename std::enable_if<vstd::is_shared_ptr<V>::value>::type* =0 ) {
        return CSerializerFunction<T,std::shared_ptr<CGameObject>>::serialize ( deserialized );
    }
    template<typename T=Serialized,typename V=Deserialized>
    static V deserialize ( std::shared_ptr<CMap> map,T serialized,typename std::enable_if<vstd::is_shared_ptr<V>::value>::type* =0 ) {
        return std::dynamic_pointer_cast<typename V::element_type> ( CSerializerFunction<T,std::shared_ptr<CGameObject>>::deserialize ( map,serialized ) );
    }
    template<typename T=Serialized,typename V=Deserialized>
    static T serialize ( V deserialized ,typename std::enable_if<vstd::is_set<V>::value>::type* =0 ) {
        return CSerializerFunction<T,std::set<std::shared_ptr<CGameObject>>>::serialize ( cast<std::set<std::shared_ptr<CGameObject>>> ( deserialized ) );
    }
    template<typename T=Serialized,typename V=Deserialized>
    static V deserialize ( std::shared_ptr<CMap> map,T serialized,typename std::enable_if<vstd::is_set<V>::value>::type* =0 ) {
        return cast<V> ( CSerializerFunction<T,std::set<std::shared_ptr<CGameObject>>>::deserialize ( map, serialized ) );
    }
    template<typename T=Serialized,typename V=Deserialized>
    static T serialize ( V deserialized ,typename std::enable_if<vstd::is_map<V>::value>::type* =0 ) {
        return CSerializerFunction<T,std::map<QString, std::shared_ptr<CGameObject> >>::serialize ( cast<std::map<QString, std::shared_ptr<CGameObject> >> ( deserialized ) );
    }
    template<typename T=Serialized,typename V=Deserialized>
    static V deserialize ( std::shared_ptr<CMap> map,T serialized,typename std::enable_if<vstd::is_map<V>::value>::type* =0 ) {
        return cast<V> ( CSerializerFunction<T,std::map<QString, std::shared_ptr<CGameObject> >>::deserialize ( map, serialized ) );
    }
};

//inline this functions
extern std::set<std::shared_ptr<CGameObject> > array_deserialize ( std::shared_ptr<CMap> map, std::shared_ptr<QJsonArray> object );
extern std::shared_ptr<QJsonArray> array_serialize ( std::set<std::shared_ptr<CGameObject> > set );
extern std::map<QString, std::shared_ptr<CGameObject> > map_deserialize ( std::shared_ptr<CMap> map, std::shared_ptr<QJsonObject> object );
extern std::shared_ptr<QJsonObject> map_serialize ( std::map<QString, std::shared_ptr<CGameObject> > object );
extern std::shared_ptr<CGameObject> object_deserialize ( std::shared_ptr<CMap> map, std::shared_ptr<QJsonObject> config );
extern std::shared_ptr<QJsonObject> object_serialize ( std::shared_ptr<CGameObject> object );

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
        registry() [std::make_pair ( qRegisterMetaType<Serialized>(),qRegisterMetaType<Deserialized>() )]=this->shared_from_this();
    }
};

class CSerialization {
public:
    template <typename Serialized,typename Deserialized>
    static Serialized serialize ( Deserialized deserialized ) {
        QVariant variant=CSerializerBase::registry() [std::make_pair ( qRegisterMetaType<Serialized>(),qRegisterMetaType<Deserialized>() )]
                         ->serialize ( QVariant::fromValue ( deserialized ) );
        return variant.value<Serialized>();
    }
    template <typename Serialized,typename Deserialized>
    static Deserialized deserialize ( std::shared_ptr<CMap> map, Serialized serialized ) {
        QVariant variant=CSerializerBase::registry() [std::make_pair ( qRegisterMetaType<Serialized>(),qRegisterMetaType<Deserialized>() )]
                         ->deserialize ( map,QVariant::fromValue ( serialized ) );
        return variant.value<Deserialized>();
    }
    static void setProperty ( std::shared_ptr<CGameObject> object , QString key, const QJsonValue &value );
    static void setProperty ( std::shared_ptr<QJsonObject> conf, QString propertyName, QVariant propertyValue );
    template<typename Class>
    static void make_serializable() {
        std::make_shared<CSerializer<std::shared_ptr<QJsonObject>,std::shared_ptr<Class>>>()->reg();
        std::make_shared<CSerializer<std::shared_ptr<QJsonArray>,std::set<std::shared_ptr<Class>>>>()->reg();
        std::make_shared<CSerializer<std::shared_ptr<QJsonObject>,std::map<QString, std::shared_ptr<Class>>>>()->reg();
    }
private:
    static QMetaProperty getProperty ( std::shared_ptr<CGameObject> object , QString name );
    static int getGenericPropertyType ( std::shared_ptr<QJsonObject> object );

    static void setArrayProperty ( std::shared_ptr<CGameObject> object, QMetaProperty property, std::shared_ptr<QJsonArray> prop );
    static void setObjectProperty ( std::shared_ptr<CGameObject> object, QMetaProperty property, std::shared_ptr<QJsonObject> prop );
    static void setStringProperty ( std::shared_ptr<CGameObject> object, QString key, QString value );
    static void setOtherProperty ( int serializedId, int deserializedId, std::shared_ptr<CGameObject> object, QMetaProperty property, QVariant variant );
};

Q_DECLARE_METATYPE ( std::shared_ptr<QJsonObject> )
Q_DECLARE_METATYPE ( std::shared_ptr<QJsonArray> )

