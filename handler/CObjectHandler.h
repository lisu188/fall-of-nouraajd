#pragma once
#include <QJsonObject>
#include <QObject>

class ATypeHandler;
class CGameObject;
class CMap;
class CObjectHandler {
public:
    CObjectHandler ( CMap *map );
    template<typename T>
    T createObject ( QString type ) const {
        CGameObject *object= _createObject ( type ) ;
        T casted=dynamic_cast<T> ( object );
        if ( casted==nullptr ) {
            delete object;
        }
        return casted;
    }
    void logProperties ( CGameObject *object ) const;
private:
    CGameObject *_createObject ( QString type ) const;
    void setProperty ( CGameObject * object , QString key, QJsonValue value ) const;
    QMetaProperty getProperty ( CGameObject * object ,QString name ) const;
    CMap *map=0;
};
