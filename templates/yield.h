#pragma once
#include "CGlobal.h"
#include "CDefines.h"
#include "templates/assert.h"
#include "templates/functional.h"

namespace vstd {
    namespace detail {

        struct yield_helper {
            static boost::thread_specific_ptr<std::function<void() >> & yield_function() {
                static boost::thread_specific_ptr<std::function<void() >> storage;
                return storage;
            }

            static boost::thread_specific_ptr<std::function<void() >> & unyield_function() {
                static boost::thread_specific_ptr<std::function<void() >> storage;
                return storage;
            }
        };

        template<typename lock>
        struct unlock {
            unlock ( lock *l ) :l ( l ) {
                this->l->unlock();
            }
            ~unlock() {
                this->l->lock();
            }
            lock *l;
        };
    }

    template<typename T=void>
    force_inline void register_yield ( std::function<void() > f ) {
        detail::yield_helper::yield_function().reset ( new std::function<void() > ( f ) );
    }

    template<typename T=void>
    force_inline void register_unyield ( std::function<void() > f ) {
        detail::yield_helper::unyield_function().reset ( new std::function<void() > ( f ) );
    }

    template<typename T=void>
    force_inline void unyield (  ) {
        if ( detail::yield_helper::unyield_function().get() ) {
            vstd::call ( *detail::yield_helper::unyield_function() );
        } else {
            vstd::fail ( "no unyield handler" );
        }
    }

    template<typename T=void>
    force_inline void yield (  ) {
        if ( detail::yield_helper::yield_function().get() ) {
            vstd::call ( *detail::yield_helper::yield_function() );
        } else {
            vstd::fail ( "no yield handler" );
        }
    }

    template<typename lock>
    force_inline void yield ( lock *l ) {
        detail::unlock<lock> u_lock ( l );
        yield();
    }

    template<typename lock,typename pred>
    force_inline void yield ( lock *l,pred p_pred ) {
        while ( !p_pred() ) {
            yield ( l );
        }
    }
}
