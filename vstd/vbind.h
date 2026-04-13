/*
 * MIT License
 *
 * Copyright (c) 2019 Andrzej Lis
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */
#pragma once

namespace vstd {
    namespace partial {
        using namespace std;

        struct pb_tag {
        };

        template<typename T> using result_of_t = typename result_of<T>::type;
        template<typename T> using is_prebinder = is_base_of<pb_tag, typename remove_reference<T>::type>;

        template<int N, int ...S>
        struct seq : seq<N - 1, N, S...> {
        };
        template<int ...S>
        struct seq<0, S...> {
            typedef seq type;
        };

        template<typename T>
        auto dispatchee(T t, false_type) -> decltype(t) {
            return t;
        }

        template<typename T>
        auto dispatchee(T t, true_type) -> decltype(t()) {
            return t();
        }

        template<typename T>
        auto expand(T t) -> decltype(dispatchee(t, is_prebinder<T>())) {
            return dispatchee(t, is_prebinder<T>());
        }

        template<typename T> using expand_type = decltype(expand(declval<T>()));

        template<typename f, typename ...ltypes>
        struct prebinder : public pb_tag {
            tuple<f, ltypes...> closure;
            typedef typename seq<sizeof...(ltypes)>::type sequence;

            prebinder(f F, ltypes... largs) : closure(F, largs...) {}

            template<int ...S, typename ...rtypes>
            result_of_t<f(expand_type<ltypes>..., rtypes...)>
            apply(seq<0, S...>, rtypes ... rargs) {
                return (get<0>(closure))(expand(get<S>(closure))..., rargs...);
            }

            template<typename ...rtypes>
            result_of_t<f(expand_type<ltypes>..., rtypes...)>
            operator()(rtypes ... rargs) {
                return apply(sequence(), rargs...);
            }
        };

        template<typename f, typename ...ltypes>
        prebinder<f, ltypes...> bind(f F, ltypes ... largs) {
            return prebinder<f, ltypes...>(F, largs...);
        }
    }
}