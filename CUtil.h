#pragma once
#include "CGlobal.h"

class CGameObject;

#define PY_PROPERTY_ACCESSOR(CLASS)\
.def ( "getStringProperty",&CLASS::getStringProperty )\
.def ( "getNumericProperty",&CLASS::getNumericProperty )\
.def ( "getBoolProperty",&CLASS::getBoolProperty )\
.def ( "setStringProperty",&CLASS::setStringProperty )\
.def ( "setNumericProperty",&CLASS::setNumericProperty )\
.def ( "setBoolProperty",&CLASS::setBoolProperty )\
.def ( "incProperty",&CLASS::incProperty )\

#define NEAR(coords) {\
    Coords(coords.x + 1,coords.y,coords.z),\
    Coords(coords.x - 1,coords.y,coords.z ),\
    Coords(coords.x,coords.y + 1, coords.z ),\
    Coords(coords.x,coords.y - 1,coords.z )}

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
}

class QObject;
class CObjectData:public QMimeData {
    Q_OBJECT
public:
    CGameObject *source;
    CObjectData ( CGameObject *source );
    CGameObject *getSource() const;
};

template<typename T,typename... U>
class Lazy {
public:
    T *get ( U... parent ) {
        if ( ptr ) {
            return ptr;
        }
        return ptr=new T ( parent... );
    }
    ~Lazy() {
        delete ptr;
    }
private :
    T* ptr=nullptr;
};

template <typename T>
struct function_traits
: public function_traits<decltype ( &T::operator() ) >
  {};
// For generic types, directly use the result of the signature of its 'operator()'

template <typename ClassType, typename ReturnType, typename... Args>
struct function_traits<ReturnType ( ClassType::* ) ( Args... ) const>
// we specialize for pointers to member function
{
    enum { arity = sizeof... ( Args ) };
    // arity is the number of arguments.

    typedef ReturnType result_type;

    template <size_t i>
    struct arg {
        typedef typename std::tuple_element<i, std::tuple<Args...>>::type type;
        // the i-th argument is equivalent to the i-th tuple element of a tuple
        // composed of those arguments.
    };
};

template <typename Container,typename Value>
inline bool contains ( Container container,Value value ) {
    return container.find ( value ) !=container.end();
}

template <typename T,typename U>
T convert ( U c ) {
    T t;
    for ( auto x:c ) {
        t.insert ( x );
    }
    return t;
}
