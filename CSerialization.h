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
    static std::unordered_map<std::pair<int,int>,std::shared_ptr<CSerializerBase>>& registry();
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
private:
    static inline QMetaProperty getProperty ( std::shared_ptr<CGameObject> object , QString name );

    template<typename Property>
    static inline void setOtherProperty ( std::shared_ptr<CGameObject> object, QMetaProperty property, Property prop ) {
        _setOtherProperty (  qRegisterMetaType<Property>(),QMetaType::type ( property.typeName() ), object, property, QVariant::fromValue ( prop ) );
    }
    static inline void _setOtherProperty ( int serializedId, int deserializedId,  std::shared_ptr<CGameObject> object, QMetaProperty property, QVariant variant );
};

namespace std {
template<bool B, typename T = void> using disable_if = std::enable_if<!B, T>;
}

template<class T, class R = void>
struct enable_if_type { typedef R type; };

template<class T, class Enable = void>
struct is_shared_ptr : std::false_type {};

template<class T>
struct is_shared_ptr<T, typename enable_if_type<typename T::element_type>::type> : std::true_type
{};

template<class T, class Enable = void>
struct is_set : std::false_type {};

template<class T>
struct is_set<T, typename std::enable_if<std::is_same<typename T::key_type,typename T::value_type>::value>::type> : std::true_type
{};

template<class T, class E1 = void,class E2 = void,class E3 = void>
struct is_map : std::false_type {};

template<class T>
struct is_map<T, typename enable_if_type<typename T::key_type>::type, typename enable_if_type<typename T::value_type>::type,typename std::disable_if<is_set<T>::value>::type> : std::true_type
{};

template<class T,  class E1 = void,class E2 = void>
struct is_pair : std::false_type {};

template<class T>
struct is_pair<T, typename enable_if_type<typename T::first_type>::type,typename enable_if_type<typename T::first_type>::type> : std::true_type
{};

namespace std {
template<bool B, typename T = void> using disable_if = std::enable_if<!B, T>;
}

template <typename T,typename U>
inline T cast ( U ptr,
                typename std::disable_if<is_shared_ptr<T>::value>::type* =0,
                typename std::disable_if<is_shared_ptr<U>::value>::type* =0,
                typename std::disable_if<is_pair<T>::value>::type* =0,
                typename std::disable_if<is_pair<U>::value>::type* =0 ) {
    return ptr;
}

template <typename T,typename U>
inline std::shared_ptr<T> cast ( U ptr,
                                 typename std::disable_if<is_shared_ptr<T>::value>::type* = 0,
                                 typename std::enable_if<is_shared_ptr<U>::value>::type* = 0 ) {
    return std::dynamic_pointer_cast<T> ( ptr );
}

template <typename T,typename U>
inline T cast ( U ptr,
                typename std::enable_if<is_shared_ptr<T>::value>::type* = 0,
                typename std::enable_if<is_shared_ptr<U>::value>::type* = 0 ) {
    return cast<typename T::element_type> ( ptr );
}

template <typename T,typename U>
inline T cast ( U ptr,
                typename std::enable_if<is_pair<T>::value>::type* = 0,
                typename std::enable_if<is_pair<U>::value>::type* = 0 ) {
    return std::make_pair ( cast<typename T::first_type> ( ptr.first ),cast<typename T::second_type> ( ptr.second ) );
}

template <typename T>
struct function_traits
: public function_traits<decltype ( &T::operator() ) >
  {};

template <typename ClassType, typename ReturnType, typename... Args>
struct function_traits<ReturnType ( ClassType::* ) ( Args... ) const> {
    enum { arity = sizeof... ( Args ) };

    typedef ReturnType result_type;

    template <size_t i>
    struct arg {
        typedef typename std::tuple_element<i, std::tuple<Args...>>::type type;
    };
};

template <typename T,typename U>
inline T convert ( U c ) {
    T t;
    for ( auto x:c ) {
        t.insert ( cast<typename T::value_type> ( x ) );
    }
    return t;
}

template <typename Serialized,typename Deserialized>
class CSerializerFunction   {
public:
    template<typename T=Serialized,typename V=Deserialized>
    static T serialize ( V deserialized,typename std::enable_if<is_shared_ptr<V>::value>::type* =0 ) {
        return CSerializerFunction<T,std::shared_ptr<CGameObject>>::serialize ( deserialized );
    }
    template<typename T=Serialized,typename V=Deserialized>
    static V deserialize ( std::shared_ptr<CMap> map,T serialized,typename std::enable_if<is_shared_ptr<V>::value>::type* =0 ) {
        return std::dynamic_pointer_cast<typename V::element_type> ( CSerializerFunction<T,std::shared_ptr<CGameObject>>::deserialize ( map,serialized ) );
    }
    template<typename T=Serialized,typename V=Deserialized>
    static T serialize ( V deserialized ,typename std::enable_if<is_set<V>::value>::type* =0 ) {
        return CSerializerFunction<T,std::set<std::shared_ptr<CGameObject>>>::serialize ( convert<std::set<std::shared_ptr<CGameObject>>> ( deserialized ) );
    }
    template<typename T=Serialized,typename V=Deserialized>
    static V deserialize ( std::shared_ptr<CMap> map,T serialized,typename std::enable_if<is_set<V>::value>::type* =0 ) {
        return convert<V> ( CSerializerFunction<T,std::set<std::shared_ptr<CGameObject>>>::deserialize ( map, serialized ) );
    }
    template<typename T=Serialized,typename V=Deserialized>
    static T serialize ( V deserialized ,typename std::enable_if<is_map<V>::value>::type* =0 ) {
        return CSerializerFunction<T,std::map<QString, std::shared_ptr<CGameObject> >>::serialize ( convert<std::map<QString, std::shared_ptr<CGameObject> >> ( deserialized ) );
    }
    template<typename T=Serialized,typename V=Deserialized>
    static V deserialize ( std::shared_ptr<CMap> map,T serialized,typename std::enable_if<is_map<V>::value>::type* =0 ) {
        return convert<V> ( CSerializerFunction<T,std::map<QString, std::shared_ptr<CGameObject> >>::deserialize ( map, serialized ) );
    }
};

extern std::set<std::shared_ptr<CGameObject> > array_deserialize ( std::shared_ptr<CMap> map, std::shared_ptr<QJsonArray> object );
extern std::shared_ptr<QJsonArray> array_serialize ( std::set<std::shared_ptr<CGameObject> > set );
extern std::map<QString, std::shared_ptr<CGameObject> > map_deserialize ( std::shared_ptr<CMap> map, std::shared_ptr<QJsonObject> object );
extern std::shared_ptr<QJsonObject> map_serialize ( std::map<QString, std::shared_ptr<CGameObject> > object );
extern std::shared_ptr<CGameObject> object_deserialize ( std::shared_ptr<CMap> map, std::shared_ptr<QJsonObject> config );
extern std::shared_ptr<QJsonObject> object_serialize ( std::shared_ptr<CGameObject> object );

template<>
class CSerializerFunction<std::shared_ptr<QJsonObject>,std::shared_ptr<CGameObject>> {
public:
    static std::shared_ptr<QJsonObject> serialize ( std::shared_ptr<CGameObject> object ) {
        return object_serialize ( object );
    }

    static std::shared_ptr<CGameObject> deserialize ( std::shared_ptr<CMap> map, std::shared_ptr<QJsonObject> config ) {
        return object_deserialize ( map,config );
    }
};

template<>
class CSerializerFunction<std::shared_ptr<QJsonObject>,std::map<QString, std::shared_ptr<CGameObject> >> {
public:
    static std::shared_ptr<QJsonObject> serialize ( std::map<QString, std::shared_ptr<CGameObject> > object ) {
        return map_serialize ( object );
    }

    static std::map<QString,std::shared_ptr<CGameObject> > deserialize ( std::shared_ptr<CMap> map,std::shared_ptr<QJsonObject> object ) {
        return map_deserialize ( map,object );
    }
};

template<>
class CSerializerFunction<std::shared_ptr<QJsonArray>,std::set<std::shared_ptr<CGameObject> >> {
public:
    static std::shared_ptr<QJsonArray> serialize ( std::set<std::shared_ptr<CGameObject> > set ) {
        return array_serialize ( set );
    }

    static std::set<std::shared_ptr<CGameObject> > deserialize ( std::shared_ptr<CMap> map,std::shared_ptr<QJsonArray> object ) {
        return array_deserialize ( map,object );
    }
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

template<typename Class>
void make_serializable() {
    std::make_shared<CSerializer<std::shared_ptr<QJsonObject>,std::shared_ptr<Class>>>()->reg();
    std::make_shared<CSerializer<std::shared_ptr<QJsonObject>,std::map<QString, std::shared_ptr<Class>>>>()->reg();
    std::make_shared<CSerializer<std::shared_ptr<QJsonArray>,std::set<std::shared_ptr<Class>>>>()->reg();
}

Q_DECLARE_METATYPE ( std::shared_ptr<QJsonObject> )
Q_DECLARE_METATYPE ( std::shared_ptr<QJsonArray> )

