#pragma once
#include "CGlobal.h"
#include "CUtil.h"

class ATypeHandler;
class CGameObject;
class CMap;
class CObjectHandler {
public:
    CObjectHandler ( std::shared_ptr<CObjectHandler> parent=std::shared_ptr<CObjectHandler>() );
    template<typename T=CGameObject>
    std::shared_ptr<T> createObject ( std::shared_ptr<CMap> map,QString type )  {
        std::shared_ptr<T> object= cast<T,CGameObject> ( _createObject ( map, type ) ) ;
        if ( object.get() ) {
            return object;
        } else if ( parent.lock().get() ) {
            return parent.lock()->createObject<T> ( map,type );
        }
        return object;
    }
    template<typename T>
    std::shared_ptr<T> clone ( std::shared_ptr<CMap> map,std::shared_ptr<T> object ) {
        return cast<T> ( deserialize ( map,serialize ( cast<CGameObject> ( object ) ) ) );
    }
    std::set<QString> getAllTypes();

    std::shared_ptr<QJsonObject> serialize ( std::shared_ptr<CGameObject> object );
    std::shared_ptr<QJsonObject> serialize ( std::map<QString, std::shared_ptr<CGameObject> > object );
    std::shared_ptr<QJsonArray> serialize ( std::set<std::shared_ptr<CGameObject> > set );

    std::shared_ptr<CGameObject> deserialize ( std::shared_ptr<CMap> map,std::shared_ptr<QJsonObject> object );
    std::set<std::shared_ptr<CGameObject> > deserialize ( std::shared_ptr<CMap> map,std::shared_ptr<QJsonArray> object );
    std::map<QString,std::shared_ptr<CGameObject> > _deserialize ( std::shared_ptr<CMap> map,std::shared_ptr<QJsonObject> object );

    void registerConfig ( QString path );
    void registerType ( QString name, std::function<CGameObject*() > constructor );
    template<typename T>
    void registerType () {
        registerType ( T::staticMetaObject.className(),[]() {return new T();} );
    }
private:
    std::shared_ptr<CGameObject> _createObject ( std::shared_ptr<CMap> map, QString type );

    std::shared_ptr<CGameObject> getType ( QString name );
    std::shared_ptr<QJsonObject> getConfig ( QString type );

    void setProperty ( std::shared_ptr<CGameObject> object , QString key, const QJsonValue &value );
    QMetaProperty getProperty ( std::shared_ptr<CGameObject> object , QString name ) ;

    void setObjectProperty ( std::shared_ptr<CGameObject> object, QMetaProperty property, std::shared_ptr<QJsonObject> propObject );
    void setArrayProperty ( std::shared_ptr<CGameObject> object, QMetaProperty property, std::shared_ptr<QJsonArray> arrayObject );
    void setMapProperty ( std::shared_ptr<CGameObject> object, QMetaProperty property, std::shared_ptr<QJsonObject> obj ) ;

    void setGenericProperty ( std::shared_ptr<QJsonObject> conf, QString propertyName, QVariant propertyValue );

    std::unordered_map<QString,std::function<CGameObject*() >>  constructors;

    std::unordered_map<QString,std::shared_ptr<QJsonObject>> objectConfig;

    std::weak_ptr<CObjectHandler> parent;

};
