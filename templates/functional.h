#pragma once

namespace vstd {
    template<typename R,typename F,typename... Args>
    R call ( F f, Args... args ) {
        return f ( args... );
    }

    template<typename F,typename... Args>
    void call ( F f, Args... args ) {
        f ( args... );
    }
}
