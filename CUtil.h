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
    std::shared_ptr<CGameObject> source;
    CObjectData ( std::shared_ptr<CGameObject> object );
    std::shared_ptr<CGameObject> getSource() const;
};

template<typename T,typename... U>
class Lazy {
public:
    std::shared_ptr<T> get ( U... parent ) {
        if ( ptr.get() ) {
            return ptr;
        }
        return ptr=std::make_shared<T> ( parent... );
    }
private :
    std::shared_ptr<T> ptr;
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
inline bool ctn ( Container &container,Value &value ) {
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

template<typename T>
QString to_hex ( T object ) {
    std::stringstream stream;
    stream << std::hex << object;
    return QString::fromStdString ( stream.str() ).toUpper();
}

template<typename T>
QString to_hex_hash ( T object ) {
    return to_hex ( std::hash<T>() ( object ) );
}

template <typename T,typename U>
std::shared_ptr<T> cast ( std::shared_ptr<U> ptr ) {
    return std::dynamic_pointer_cast<T> ( ptr );
}
