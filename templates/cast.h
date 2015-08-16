#pragma once

#include "CDefines.h"
#include "templates/traits.h"

namespace vstd {
    template <typename T,typename U>
    force_inline T cast ( U ptr,
                          typename vstd::disable_if<vstd::is_shared_ptr<T>::value>::type* =0,
                          typename vstd::disable_if<vstd::is_shared_ptr<U>::value>::type* =0,
                          typename vstd::disable_if<vstd::is_container<T>::value>::type* =0,
                          typename vstd::disable_if<vstd::is_container<U>::value>::type* =0,
                          typename vstd::disable_if<vstd::is_pair<T>::value>::type* =0,
                          typename vstd::disable_if<vstd::is_pair<U>::value>::type* =0 ) {
        return ptr;
    }

    template <typename T,typename U>
    force_inline std::shared_ptr<T> cast ( U ptr,
                                           typename vstd::disable_if<vstd::is_shared_ptr<T>::value>::type* = 0,
                                           typename vstd::enable_if<vstd::is_shared_ptr<U>::value>::type* = 0 ) {
        return std::dynamic_pointer_cast<T> ( ptr );
    }

    template <typename T,typename U>
    force_inline T cast ( U ptr,
                          typename vstd::enable_if<vstd::is_shared_ptr<T>::value>::type* = 0,
                          typename vstd::enable_if<vstd::is_shared_ptr<U>::value>::type* = 0 ) {
        return cast<typename T::element_type> ( ptr );
    }

    template <typename T,typename U>
    force_inline T cast ( U ptr,
                          typename std::enable_if<vstd::is_pair<T>::value>::type* = 0,
                          typename std::enable_if<vstd::is_pair<U>::value>::type* = 0 ) {
        return std::make_pair ( cast<typename T::first_type> ( ptr.first ),cast<typename T::second_type> ( ptr.second ) );
    }

    template <typename T,typename U>
    force_inline T cast ( U c ,
                          typename std::enable_if<vstd::is_container<T>::value>::type* = 0,
                          typename std::enable_if<vstd::is_container<U>::value>::type* = 0 ) {
        T t;
        for ( typename U::value_type x:c ) {
            t.insert ( cast<typename T::value_type> ( x ) );
        }
        return t;
    }
}
