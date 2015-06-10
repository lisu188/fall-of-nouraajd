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
        if ( object ) {
            return object;
        } else if ( parent.lock() ) {
            return parent.lock()->createObject<T> ( map,type );
        }
        return object;
    }
    template<typename T>
    std::shared_ptr<T> clone ( std::shared_ptr<T> object ) {
        return cast<T> ( _clone ( object ) );
    }
    std::set<QString> getAllTypes();

    void registerConfig ( QString path );
    void registerType ( QString name, std::function<CGameObject*() > constructor );
    template<typename T>
    void registerType () {
        registerType ( T::staticMetaObject.className(),[]() {return new T();} );
    }
    std::shared_ptr<CGameObject> getType ( QString name );
    std::shared_ptr<QJsonObject> getConfig ( QString type );
private:
    std::shared_ptr<CGameObject> _createObject ( std::shared_ptr<CMap> map, QString type );
    std::shared_ptr<CGameObject> _clone ( std::shared_ptr<CGameObject> object );

    std::unordered_map<QString,std::function<CGameObject*() >>  constructors;

    std::unordered_map<QString,std::shared_ptr<QJsonObject>> objectConfig;

    std::weak_ptr<CObjectHandler> parent;

};
