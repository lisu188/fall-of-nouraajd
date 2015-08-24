#pragma once
#include "CDefines.h"
#include "CUtil.h"
#include "templates/traits.h"
#include "templates/functional.h"

namespace vstd {
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
        static force_inline std::size_t hash ( U u,
                                               typename vstd::disable_if<vstd::is_pair<U>::value>::type* =0,
                                               typename vstd::disable_if<vstd::is_enum<U>::value>::type* =0 ) {
            return call ( std::hash<U>() , u );
        }
        template<typename U=T>
        static force_inline std::size_t hash ( U u,
                                               typename vstd::disable_if<vstd::is_pair<U>::value>::type* =0,
                                               typename vstd::enable_if<vstd::is_enum<U>::value>::type* =0 ) {
            return hasher<int>::hash ( static_cast<int> ( u ) );
        }
    };

    template<typename T>
    force_inline std::size_t hash_combine ( T t ) {
        return hasher<T>::hash ( t );
    }

    template <typename F,typename G,typename ...T>
    force_inline std::size_t hash_combine ( F f,G g,T... args ) {
        return power<31,sizeof... ( args )+1>::value *
               hash_combine ( f ) +
               hash_combine ( g, args... );
    }
}

namespace std {
    template<>
    struct hash<Coords> {
        force_inline std::size_t operator() ( const Coords &coords ) const {
            return vstd::hash_combine ( coords.x,coords.y,coords.z );
        }
    };

    template<>
    struct hash<QString> {
        force_inline std::size_t operator() ( const QString &string ) const {
            return vstd::hash_combine ( string.toStdString() );
        }
    };

    template<>
    struct hash<std::pair<int,int>> {
        force_inline std::size_t operator() ( const std::pair<int,int> &pair ) const {
            return vstd::hash_combine ( pair.first,pair.second );
        }
    };
}
