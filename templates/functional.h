#pragma once
#include "CDefines.h"
#include"templates/traits.h"

namespace vstd {
    template<typename R,typename F,typename... Args>
    force_inline R call ( F f, Args... args ) {
        return f ( args... );
    }

    template<typename F,typename... Args>
    force_inline void call ( F f, Args... args ) {
        f ( args... );
    }

    template<typename Ctn,typename Func >
    force_inline std::set<typename function_traits<Func>::return_type> map ( Ctn ctn,Func f ) {
        typedef typename function_traits<Func>::return_type Return;
        std::set<Return> ret;
        for ( typename Ctn::value_type val:ctn ) {
            ret.insert ( call<Return> ( f,val ) );
        }
        return ret;
    }

    template<typename Ctn>
    class stream {
    public:
        typename Ctn::iterator begin() {
            return ctn.begin();
        }
        typename Ctn::iterator end() {
            return ctn.end();
        }
    private:
        Ctn ctn;
    };
}
