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

class CInvokeLater:public QObject,public QRunnable {
    Q_OBJECT
public:
    CInvokeLater ( std::function<void () > target );
    void run() override;
    std::function<void() > target;
    Q_INVOKABLE void call();
};

