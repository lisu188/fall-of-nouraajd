#pragma once
#include "CGlobal.h"
#include "templates/traits.h"
#include "templates/hash.h"

class CGameObject;

#define GAME_PROPERTY(CLASS)\
  Q_DECLARE_METATYPE(std::shared_ptr<CLASS>)\
  Q_DECLARE_METATYPE(std::set<std::shared_ptr<CLASS>>)\
  typedef std::map<QString,std::shared_ptr<CLASS>> CLASS##Map;\
  Q_DECLARE_METATYPE(CLASS##Map)\

#define PY_SAFE(x) try{x}catch(...){qDebug()<<"";PyErr_Print();PyErr_Clear();}
#define PY_SAFE_RET(x) try{x}catch(...){qDebug()<<"";PyErr_Print();PyErr_Clear();return nullptr;}

struct Coords {
    Coords();
    Coords ( int x, int y, int z );
    int x, y, z;
    bool operator== ( const Coords &other ) const;
    bool operator< ( const Coords &other ) const;
    Coords operator- ( const Coords &other ) const;
    Coords operator*() const;
    double getDist ( Coords a );
};

class QObject;
class CObjectData:public QMimeData {
    Q_OBJECT
public:
    std::shared_ptr<CGameObject> source;
    CObjectData ( std::shared_ptr<CGameObject> object );
    std::shared_ptr<CGameObject> getSource() const;
};

namespace std {
    template<>
    struct hash<Coords> {
        std::size_t operator() ( const Coords &coords ) const;
    };

    template<>
    struct hash<QString> {
        std::size_t operator() ( const QString &string ) const;
    };

    template<>
    struct hash<std::pair<int,int>> {
        std::size_t operator() ( const std::pair<int,int> &pair ) const;
    };
}

namespace vstd {
    template <typename Container,typename Value>
    bool ctn ( Container &container,Value value ) {
        return container.find ( value ) !=container.end();
    }

    template <typename T,typename U>
    bool castable ( std::shared_ptr<U> ptr ) {
        return std::dynamic_pointer_cast<T> ( ptr ).operator bool();
    }

    template <typename A,typename B>
    std::pair<int,int> type_pair() {
        return std::make_pair ( qRegisterMetaType<A>(),qRegisterMetaType<B>() );
    }
}

