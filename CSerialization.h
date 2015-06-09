#pragma once
#include "CGlobal.h"
#include "CMap.h"

class CMap;

class CSerialization {
public:
    static std::shared_ptr<QJsonObject> serialize ( std::shared_ptr<CGameObject> object );
    static std::shared_ptr<QJsonObject> serialize ( std::map<QString, std::shared_ptr<CGameObject> > object );
    static std::shared_ptr<QJsonArray> serialize ( std::set<std::shared_ptr<CGameObject> > set );

    static std::shared_ptr<CGameObject> deserialize ( std::shared_ptr<CMap> map, std::shared_ptr<QJsonObject> config );
    static std::set<std::shared_ptr<CGameObject> > deserialize ( std::shared_ptr<CMap> map,std::shared_ptr<QJsonArray> object );
    static std::map<QString,std::shared_ptr<CGameObject> > _deserialize ( std::shared_ptr<CMap> map,std::shared_ptr<QJsonObject> object );
private:
    static void setProperty ( std::shared_ptr<CGameObject> object , QString key, const QJsonValue &value );
    static QMetaProperty getProperty ( std::shared_ptr<CGameObject> object , QString name );

    static void setGenericProperty ( std::shared_ptr<QJsonObject> conf, QString propertyName, QVariant propertyValue );

    static void setObjectProperty ( std::shared_ptr<CGameObject> object, QMetaProperty property, std::shared_ptr<QJsonObject> propObject );
    static void setArrayProperty ( std::shared_ptr<CGameObject> object, QMetaProperty property, std::shared_ptr<QJsonArray> arrayObject );
    static void setMapProperty ( std::shared_ptr<CGameObject> object, QMetaProperty property, std::shared_ptr<QJsonObject> obj );
};
