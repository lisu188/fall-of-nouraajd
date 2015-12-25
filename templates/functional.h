#pragma once

#include "templates/defines.h"
#include "templates/traits.h"

namespace vstd {
    template<typename F, typename... Args>
    force_inline
    typename disable_if<is_void<typename function_traits<F>::return_type>::value,
            typename function_traits<F>::return_type>::type call(F f, Args... args) {
        return f(args...);
    }

    template<typename F, typename... Args>
    force_inline
    typename enable_if<is_void<typename function_traits<F>::return_type>::value,
            typename function_traits<F>::return_type>::type call(F f, Args... args) {
        f(args...);
    }

    template<typename Ctn, typename Func>
    force_inline std::set<typename function_traits<Func>::return_type> map(Ctn ctn, Func f) {
        typedef typename function_traits<Func>::return_type Return;
        std::set<Return> ret;
        for (typename Ctn::value_type val:ctn) {
            ret.insert(call<Return>(f, val));
        }
        return ret;
    }

    template<typename Ctn, typename Func>
    force_inline void map(Ctn ctn, Func f) {
        for (typename function_traits<Func>::return_type val:ctn) {
            call(f, val);
        }
    }
}
