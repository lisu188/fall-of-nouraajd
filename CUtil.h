#pragma once
#include "CGlobal.h"
#include "CTraits.h"

class CGameObject;

#define GAME_PROPERTY(CLASS)\
  Q_DECLARE_METATYPE(std::shared_ptr<CLASS>)\
  Q_DECLARE_METATYPE(std::set<std::shared_ptr<CLASS>>)\
  typedef std::map<QString,std::shared_ptr<CLASS>> CLASS##Map;\
  Q_DECLARE_METATYPE(CLASS##Map)\

template<typename T,typename U=int>
U fail_if ( T arg,QString msg ) {
    if ( arg ) {
        qFatal ( msg.toStdString().c_str() );
    }
    return U();
}

template<typename T=int>
T fail ( QString msg ) {
    return fail_if<bool,T> ( true,msg );
}

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

template <int a,int x>
struct power {
    enum { value = a * power<a,x - 1>::value };
};

template <int a>
struct power<a,0> {
    enum { value = 1 };
};

template<typename T>
struct hasher {
    template<typename U=T>
    static std::size_t hash ( U u,typename vstd::disable_if<std::is_enum<U>::value>::type* =0 ) {
        return std::hash<U>() ( u );
    }
    template<typename U=T>
    static std::size_t hash ( U u,typename vstd::enable_if<std::is_enum<U>::value>::type* =0 ) {
        return hasher<int>::hash ( static_cast<int> ( u ) );
    }
};

template<typename T>
std::size_t hash_combine ( T t ) {
    return hasher<T>::hash ( t );
}

template <typename F,typename G,typename ...T>
std::size_t hash_combine ( F f,G g,T... args ) {
    return power<31,sizeof... ( args )+1>::value *
           hash_combine ( f ) +
           hash_combine ( g, args... );
}

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
bool ctn ( Container &container,Value value ) {
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
    return to_hex ( long ( object ) );
}

template<typename T>
QString to_hex ( std::shared_ptr<T> object ) {
    return to_hex ( object.get() );
}

template<typename T>
QString to_hex_hash ( T object ) {
    return to_hex ( hash_combine ( object ) );
}

template <typename T,typename U>
bool castable ( std::shared_ptr<U> ptr ) {
    return std::dynamic_pointer_cast<T> ( ptr ).operator bool();
}

namespace vstd {
    template<typename R,typename F,typename... Args>
    R call ( F f, Args... args ) {
        return f ( args... );
    }

    template<typename F,typename... Args>
    void call ( F f, Args... args ) {
        f ( args... );
    }
    template <typename T>
    T not_null ( T t,QString msg="" ) {
        if ( t ) {
            return t;
        }
        return fail<T> ( msg );
    }

}

