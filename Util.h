#pragma once
#include <QMimeData>
#include <QString>
#include <QThreadPool>
#include <functional>
class CGameObject;

#define PY_PROPERTY_ACCESSOR(CLASS)\
.def ( "getStringProperty",&CLASS::getStringProperty )\
.def ( "getNumericProperty",&CLASS::getNumericProperty )\
.def ( "getBoolProperty",&CLASS::getBoolProperty )\
.def ( "setStringProperty",&CLASS::setStringProperty )\
.def ( "setNumericProperty",&CLASS::setNumericProperty )\
.def ( "setBoolProperty",&CLASS::setBoolProperty )\
.def ( "incProperty",&CLASS::incProperty )\

struct Coords {
    Coords();
    Coords ( int x, int y, int z );
    int x, y, z;
    bool operator== ( const Coords &other ) const;
    bool operator< ( const Coords &other ) const;
    Coords operator- ( const Coords &other ) const;
    int getDist ( Coords a );
};

namespace std {
template<>
struct hash<Coords> {
    std::size_t operator() ( const Coords &coords ) const;
};

template<>
struct hash<QString> {
    std::hash<std::string> stringHash;
    std::size_t operator() ( const QString &string ) const;
};
}

class QObject;
class CObjectData:public QMimeData {
    Q_OBJECT
public:
    CGameObject *source;
    CObjectData ( CGameObject *source );
    CGameObject *getSource() const;
};

template<typename T,typename U>
class Lazy {
public:
    T*get ( U*parent ) {
        if ( ptr ) {
            return ptr;
        }
        return ptr=new T ( parent );
    }
private :
    T*ptr=nullptr;
};
