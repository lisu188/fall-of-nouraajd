#pragma once

namespace vstd {
    template<bool B, typename T = void> using enable_if = std::enable_if<B, T>;
    template<bool B, typename T = void> using disable_if = std::enable_if<!B, T>;

    using std::is_enum;
    using std::is_same;
    using std::is_base_of;

    template<class T, class R = void>
    struct enable_if_type { typedef R type; };

    template<class T, class Enable = void>
    struct is_shared_ptr : std::false_type {};

    template<class T>
    struct is_shared_ptr<T, typename enable_if_type<typename T::element_type>::type> : std::true_type
    {};

    template<class T, class Enable = void>
    struct is_set : std::false_type {};

    template<class T>
    struct is_set<T, typename std::enable_if<std::is_same<typename T::key_type,typename T::value_type>::value>::type> : std::true_type
    {};

    template<class T, class E1 = void,class E2 = void,class E3 = void>
    struct is_map : std::false_type {};

    template<class T>
    struct is_map<T, typename enable_if_type<typename T::key_type>::type, typename enable_if_type<typename T::value_type>::type,typename disable_if<is_set<T>::value>::type> : std::true_type
    {};

    template<class T, class E1 = void,class E2 = void>
    struct is_pair : std::false_type {};

    template<class T>
    struct is_pair<T, typename enable_if_type<typename T::first_type>::type,typename enable_if_type<typename T::second_type>::type> : std::true_type
    {};

    template<class T, class E1 = void,class E2=void>
    struct is_container : std::false_type {};

    template<class T>
    struct is_container<T, typename enable_if_type<typename T::value_type>::type,typename disable_if<std::is_same<
        typename std::remove_reference<
        typename std::remove_cv<T>::type>::type,QString>::value>::type> : std::true_type
    {};

    template <typename T>
    struct function_traits
    : public function_traits<decltype ( &T::operator() ) >
      {};

    template <typename ClassType, typename ReturnType, typename... Args>
    struct function_traits<ReturnType ( ClassType::* ) ( Args... ) const> {
        enum { arity = sizeof... ( Args ) };

        typedef ReturnType return_type;

        template <size_t i>
        struct arg {
            typedef typename std::tuple_element<i, std::tuple<Args...>>::type type;
        };
    };
}


