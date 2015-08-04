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

template<>
struct hash<std::pair<int,int>> {
    std::size_t operator() ( const std::pair<int,int> &pair ) const;
};
}

template<int n>
struct prime {

};

template<>
struct prime<0> {
    static const int value=13;
};

template<>
struct prime<1> {
    static const int value=17;
};

template<>
struct prime<2> {
    static const int value=19;
};

template<>
struct prime<3> {
    static const int value=23;
};

inline std::size_t int_hash();

template <typename F,typename ...T>
inline std::size_t int_hash ( F f,T... args ) {
    return f*prime<sizeof... ( args ) >::value*int_hash ( args... );
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
inline bool ctn ( Container &container,Value &value ) {
    return container.find ( value ) !=container.end();
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
inline bool castable ( std::shared_ptr<U> ptr ) {
    return std::dynamic_pointer_cast<T> ( ptr ).operator bool();
}

