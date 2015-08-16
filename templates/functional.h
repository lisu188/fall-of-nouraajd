#pragma once
#include "CDefines.h"

namespace vstd {
    template<typename R,typename F,typename... Args>
    force_inline R call ( F f, Args... args ) {
        return f ( args... );
    }

    template<typename F,typename... Args>
    force_inline void call ( F f, Args... args ) {
        f ( args... );
    }
}
