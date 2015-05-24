#pragma once
#include "CGlobal.h"
#include "CUtil.h"

class ATypeHandler;
class CGameObject;
class CMap;
class CObjectHandler {
public:
    CObjectHandler ( std::shared_ptr<CObjectHandler> parent=std::shared_ptr<CObjectHandler>() );
    template<typename T>
    std::shared_ptr<T> createObject ( std::shared_ptr<CMap> map,QString type )  {
        std::shared_ptr<T> object= cast<T,CGameObject> ( _createObject ( map, type ) ) ;
        if ( object.get() ) {
            return object;
        } else if ( parent.lock().get() ) {
            return parent.lock()->createObject<T> ( map,type );
        }
        return object;
    }
    std::shared_ptr<CGameObject> getType ( QString name );
    QJsonObject getConfig ( QString type );

    std::set<QString> getAllTypes();
    bool isFlagSet ( QString type,QString property );

    void registerConfig ( QString path );
    void registerType ( QString name, std::function<CGameObject*() > constructor );
    template<typename T>
    void registerType () {
        registerType ( T::staticMetaObject.className(),[]() {return new T();} );
    }
private:
    std::shared_ptr<CGameObject> _createObject ( std::shared_ptr<CMap> map, QString type );

    void setProperty ( CGameObject *object , QString key, QJsonValue value ) const;
    QMetaProperty getProperty ( CGameObject *object , QString name ) const;

    void logProperties ( CGameObject *object ) const;

    std::unordered_map<QString,std::function<CGameObject*() > > constructors;
    QJsonObject objectConfig;

    std::weak_ptr<CObjectHandler> parent;
};
