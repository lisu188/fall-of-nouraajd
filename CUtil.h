#pragma once
#include "CGlobal.h"
#include "CTraits.h"

class CGameObject;

#define GAME_PROPERTY(CLASS)\
  Q_DECLARE_METATYPE(std::shared_ptr<CLASS>)\
  Q_DECLARE_METATYPE(std::set<std::shared_ptr<CLASS>>)\
  typedef std::map<QString,std::shared_ptr<CLASS>> CLASS##Map;\
  Q_DECLARE_METATYPE(CLASS##Map)\

#define PY_PROPERTY_ACCESSOR(CLASS)\
  .def ( "getStringProperty",&CLASS::getStringProperty )\
  .def ( "getNumericProperty",&CLASS::getNumericProperty )\
  .def ( "getBoolProperty",&CLASS::getBoolProperty )\
  .def ( "setStringProperty",&CLASS::setStringProperty )\
  .def ( "setNumericProperty",&CLASS::setNumericProperty )\
  .def ( "setBoolProperty",&CLASS::setBoolProperty )\
  .def ( "incProperty",&CLASS::incProperty )\

#define PY_SAFE(x) try{x}catch(...){PyErr_Print();PyErr_Clear();}
#define PY_SAFE_RET(x) try{x}catch(...){PyErr_Print();PyErr_Clear();return nullptr;}

template <typename T,typename U>
T cast ( U ptr,
         typename vstd::disable_if<vstd::is_shared_ptr<T>::value>::type* =0,
         typename vstd::disable_if<vstd::is_shared_ptr<U>::value>::type* =0,
         typename vstd::disable_if<vstd::is_container<T>::value>::type* =0,
         typename vstd::disable_if<vstd::is_container<U>::value>::type* =0,
         typename vstd::disable_if<vstd::is_pair<T>::value>::type* =0,
         typename vstd::disable_if<vstd::is_pair<U>::value>::type* =0 ) {
    return ptr;
}

template <typename T,typename U>
std::shared_ptr<T> cast ( U ptr,
                          typename vstd::disable_if<vstd::is_shared_ptr<T>::value>::type* = 0,
                          typename vstd::enable_if<vstd::is_shared_ptr<U>::value>::type* = 0 ) {
    return std::dynamic_pointer_cast<T> ( ptr );
}

template <typename T,typename U>
T cast ( U ptr,
         typename vstd::enable_if<vstd::is_shared_ptr<T>::value>::type* = 0,
         typename vstd::enable_if<vstd::is_shared_ptr<U>::value>::type* = 0 ) {
    return cast<typename T::element_type> ( ptr );
}

template <typename T,typename U>
T cast ( U ptr,
         typename std::enable_if<vstd::is_pair<T>::value>::type* = 0,
         typename std::enable_if<vstd::is_pair<U>::value>::type* = 0 ) {
    return std::make_pair ( cast<typename T::first_type> ( ptr.first ),cast<typename T::second_type> ( ptr.second ) );
}

template <typename T,typename U>
T cast ( U c ,
         typename std::enable_if<vstd::is_container<T>::value>::type* = 0,
         typename std::enable_if<vstd::is_container<U>::value>::type* = 0 ) {
    T t;
    for ( typename U::value_type x:c ) {
        t.insert ( cast<typename T::value_type> ( x ) );
    }
    return t;
}

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

    template<>
    struct hash<std::pair<int,int>> {
        std::size_t operator() ( const std::pair<int,int> &pair ) const;
    };
}

template <int a,int x>
struct power {
    enum { value = a * power<a,x - 1>::value };
};

template <int a>
struct power<a,0> {
    enum { value = 1 };
};

std::size_t int_hash();

template <typename F,typename ...T>
std::size_t int_hash ( F f,T... args ) {
    return f*power<31,sizeof... ( args ) >::value+int_hash ( args... );
}

class QObject;
class CObjectData:public QMimeData {
    Q_OBJECT
public:
    std::shared_ptr<CGameObject> source;
    CObjectData ( std::shared_ptr<CGameObject> object );
    std::shared_ptr<CGameObject> getSource() const;
};

template<typename T,typename... U>
class Lazy {
public:
    std::shared_ptr<T> get ( U... parent ) {
        if ( ptr ) {
            return ptr;
        }
        return ptr=std::make_shared<T> ( parent... );
    }
private :
    std::shared_ptr<T> ptr;
};

template <typename Container,typename Value>
bool ctn ( Container &container,Value &value ) {
    return container.find ( value ) !=container.end();
}

template<typename T>
QString to_hex ( T object ) {
    std::stringstream stream;
    stream << std::hex << object;
    return QString::fromStdString ( stream.str() ).toUpper();
}

template<typename T>
QString to_hex ( T* object ) {
    std::stringstream stream;
    stream << std::hex << ( long ) object;
    return QString::fromStdString ( stream.str() ).toUpper();
}

template<typename T>
QString to_hex ( std::shared_ptr<T> object ) {
    std::stringstream stream;
    stream << std::hex << ( long ) object.get();
    return QString::fromStdString ( stream.str() ).toUpper();
}

template<typename T>
QString to_hex_hash ( T object ) {
    return to_hex ( std::hash<T>() ( object ) );
}

template <typename T,typename U>
bool castable ( std::shared_ptr<U> ptr ) {
    return std::dynamic_pointer_cast<T> ( ptr ).operator bool();
}
