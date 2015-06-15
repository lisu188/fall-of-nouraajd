#pragma once
#include "CGlobal.h"
#include "CMap.h"

class CMap;
class CSerializerBase;

class CSerialization {
private:
    static void setProperty ( std::shared_ptr<CGameObject> object , QString key, const QJsonValue &value );
    static QMetaProperty getProperty ( std::shared_ptr<CGameObject> object , QString name );

    static void setGenericProperty ( std::shared_ptr<QJsonObject> conf, QString propertyName, QVariant propertyValue );

    static void setObjectProperty ( std::shared_ptr<CGameObject> object, QMetaProperty property, std::shared_ptr<QJsonObject> propObject );
    static void setArrayProperty ( std::shared_ptr<CGameObject> object, QMetaProperty property, std::shared_ptr<QJsonArray> arrayObject );
    static void setMapProperty ( std::shared_ptr<CGameObject> object, QMetaProperty property, std::shared_ptr<QJsonObject> obj );
};

class CSerializerBase{
    friend class CSerialization;
public:
    virtual QVariant serialize(QVariant object)=0;
    virtual QVariant deserialize(std::shared_ptr<CMap> map,QVariant object)=0;
protected:
    static std::unordered_map<std::pair<int,int>,CSerializerBase*> registry;
};

template <typename Serialized,typename Deserialized>
class CSerializerFunction{
    public:
    static Serialized serialize(Deserialized deserialized)=delete;
    static Deserialized deserialize( std::shared_ptr<CMap> map,Serialized deserialized)=delete;
};

template<>
class CSerializerFunction<std::shared_ptr<QJsonObject>,std::shared_ptr<CGameObject>>{
    public:
    static std::shared_ptr<QJsonObject> serialize ( std::shared_ptr<CGameObject> object );
    static std::shared_ptr<CGameObject> deserialize ( std::shared_ptr<CMap> map, std::shared_ptr<QJsonObject> config );
};

template<>
class CSerializerFunction<std::shared_ptr<QJsonObject>,std::map<QString, std::shared_ptr<CGameObject> >>{
    public:
    static std::shared_ptr<QJsonObject> serialize ( std::map<QString, std::shared_ptr<CGameObject> > object );
    static std::map<QString,std::shared_ptr<CGameObject> > deserialize ( std::shared_ptr<CMap> map,std::shared_ptr<QJsonObject> object );
};

template<>
class CSerializerFunction<std::shared_ptr<QJsonArray>,std::set<std::shared_ptr<CGameObject> >>{
    public:
    static std::shared_ptr<QJsonArray> serialize ( std::set<std::shared_ptr<CGameObject> > set );
    static std::set<std::shared_ptr<CGameObject> > deserialize ( std::shared_ptr<CMap> map,std::shared_ptr<QJsonArray> object );
};

template <typename Serialized,typename Deserialized>
class CSerializer:CSerializerBase{
public:
    static CSerializer<Serialized,Deserialized> value;
    virtual QVariant serialize(QVariant object) override final{
        return QVariant::fromValue(CSerializerFunction<Serialized,Deserialized>::serialize(object.value<Deserialized>()));
    }
    virtual QVariant deserialize(std::shared_ptr<CMap> map,QVariant object) override final{
         return QVariant::fromValue(CSerializerFunction<Serialized,Deserialized>::deserialize(map,object.value<Serialized>()));
    }
private:
    CSerializer(){
        registry[std::make_pair(qRegisterMetaType<Serialized>(),qRegisterMetaType<Deserialized>())]=this;
    }
};

Q_DECLARE_METATYPE(std::shared_ptr<QJsonObject>)
Q_DECLARE_METATYPE(std::shared_ptr<QJsonArray>)

