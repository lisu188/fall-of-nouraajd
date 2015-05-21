#pragma once
#include "CGlobal.h"
#include "CUtil.h"

class ATypeHandler;
class CGameObject;
class CMap;
class CObjectHandler {
public:
    CObjectHandler ( CObjectHandler *parent=nullptr );
    template<typename T>
    T createObject ( CMap *map,QString type )  {
        T object= dynamic_cast<T> ( _createObject ( map, type ) ) ;
        if ( object ) {
            return object;
        } else if ( parent ) {
            return parent->createObject<T> ( map,type );
        }
        return nullptr;
    }
    CGameObject *getType ( QString name );
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
    CGameObject *_createObject (  CMap*map,QString type );

    void setProperty ( CGameObject * object , QString key, QJsonValue value ) const;
    QMetaProperty getProperty ( CGameObject * object ,QString name ) const;

    void logProperties ( CGameObject *object ) const;

    std::unordered_map<QString,std::function<CGameObject*() > > constructors;
    QJsonObject objectConfig;

    CObjectHandler *parent=nullptr;
};
