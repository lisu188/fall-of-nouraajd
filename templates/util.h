#pragma once

#include "templates/traits.h"
#include "templates/hash.h"

namespace vstd {
    template <typename Container,typename Value>
    force_inline bool ctn ( Container &container,Value value ) {
        return container.find ( value ) !=container.end();
    }

    template <typename T,typename U>
    force_inline bool castable ( std::shared_ptr<U> ptr ) {
        return std::dynamic_pointer_cast<T> ( ptr ).operator bool();
    }

    template <typename A,typename B>
    force_inline std::pair<int,int> type_pair() {
        return std::make_pair ( qRegisterMetaType<A>(),qRegisterMetaType<B>() );
    }

    template<typename T=void>
    force_inline bool is_main_thread() {
        return QApplication::instance()->thread() == QThread::currentThread();
    }

    template<typename T=void>
    force_inline void assert_main_thread() {
        if ( !is_main_thread() ) {
            qFatal ( "not a main thread" );
        }
    }

    template<typename F,typename... Args>
    force_inline std::function<typename function_traits<F>::return_type() > bind ( F f,Args... args ) {
        return std::bind ( f,args... );
    }
}
