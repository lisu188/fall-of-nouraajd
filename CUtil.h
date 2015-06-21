#pragma once
#include "CGlobal.h"
#include "CSerialization.h"

class CGameObject;

#define GAME_PROPERTY(CLASS)\
    Q_DECLARE_METATYPE(std::shared_ptr<CLASS>)\
    Q_DECLARE_METATYPE(std::set<std::shared_ptr<CLASS>>)\
    typedef std::map<QString,std::shared_ptr<CLASS>> CLASS##Map;\
    Q_DECLARE_METATYPE(CLASS##Map)\
    namespace{\
        class CLASS##_X{\
        public:\
            CLASS##_X(){\
                qRegisterMetaType<std::shared_ptr<CLASS>>();\
                qRegisterMetaType<std::set<std::shared_ptr<CLASS>>>();\
                qRegisterMetaType<std::map<QString,std::shared_ptr<CLASS>>>();\
                make_serializable<CLASS>();\
            }\
        } CLASS##_TMP;\
    }\


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
        if ( ptr ) {
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

template <typename ClassType, typename ReturnType, typename... Args>
struct function_traits<ReturnType ( ClassType::* ) ( Args... ) const> {
    enum { arity = sizeof... ( Args ) };

    typedef ReturnType result_type;

    template <size_t i>
    struct arg {
        typedef typename std::tuple_element<i, std::tuple<Args...>>::type type;
    };
};

template <typename Container,typename Value>
inline bool ctn ( Container &container,Value &value ) {
    return container.find ( value ) !=container.end();
}

template <typename T,typename U>
inline T convert ( U c ) {
    T t;
    for ( auto x:c ) {
        t.insert ( x );
    }
    return t;
}

template<typename T>
inline QString to_hex ( T object ) {
    std::stringstream stream;
    stream << std::hex << object;
    return QString::fromStdString ( stream.str() ).toUpper();
}

template<typename T>
inline QString to_hex ( T* object ) {
    std::stringstream stream;
    stream << std::hex << ( long ) object;
    return QString::fromStdString ( stream.str() ).toUpper();
}

template<typename T>
inline QString to_hex ( std::shared_ptr<T> object ) {
    std::stringstream stream;
    stream << std::hex << ( long ) object.get();
    return QString::fromStdString ( stream.str() ).toUpper();
}

template<typename T>
inline QString to_hex_hash ( T object ) {
    return to_hex ( std::hash<T>() ( object ) );
}

template <typename T,typename U>
inline std::shared_ptr<T> cast ( std::shared_ptr<U> ptr ) {
    return std::dynamic_pointer_cast<T> ( ptr );
}

template <typename T,typename U>
inline bool castable ( std::shared_ptr<U> ptr ) {
    return std::dynamic_pointer_cast<T> ( ptr ).operator bool();
}

