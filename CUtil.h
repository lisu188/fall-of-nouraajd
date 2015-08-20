#pragma once
#include "CGlobal.h"

class CGameObject;

struct Coords {
    Coords();
    Coords ( int x, int y, int z );
    int x, y, z;
    bool operator== ( const Coords &other ) const;
    bool operator!= ( const Coords &other ) const;
    bool operator< ( const Coords &other ) const;
    bool operator> ( const Coords &other ) const;
    Coords operator- ( const Coords &other ) const;
    Coords operator+ ( const Coords &other ) const;
    Coords operator*() const;
    double getDist ( Coords a ) const;
};

class CObjectData:public QMimeData {
    Q_OBJECT
public:
    CObjectData ( std::shared_ptr<CGameObject> object );
    std::shared_ptr<CGameObject> getSource() const;
private:
    std::shared_ptr<CGameObject> source;
};

class CInvocationEvent:public QEvent {
public:
    static const QEvent::Type TYPE=static_cast<QEvent::Type> ( 1001 );
    CInvocationEvent ( std::function<void () > target );
    std::function<void () > getTarget() const;
private:
    std::function<void() > const target;
};

class CInvocationHandler:public QObject {
    Q_OBJECT
public:
    static CInvocationHandler* instance();
    bool event ( QEvent *event ) ;
private:
    CInvocationHandler();
};
