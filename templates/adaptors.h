#pragma once
#include "CGlobal.h"
#include "templates/traits.h"
#include "templates/future.h"

namespace vstd {
    namespace adaptors {
        template<typename F>
        auto add_later ( F f ) {
            return boost::adaptors::transformed ( [f] ( std::shared_ptr<
                                                  future<typename function_traits<F>::
            template arg<0>::type>>  future ) {
                return future->thenLater ( f );
            } );
        }
    }
}
