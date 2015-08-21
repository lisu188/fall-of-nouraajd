#pragma once

#include "templates/traits.h"
#include "templates/hash.h"
#include "templates/cast.h"

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

    template<typename Range,typename Value=typename range_traits<Range>::value_type>
    force_inline std::set<Value> collect ( Range r ) {
        return cast<std::set<Value>> ( r );
    }

    template<typename T>
    force_inline typename T::value_type pop ( T &t ) {
        auto x=t.front();
        t.pop();
        return x;
    }

    //TODO: use somewhere std::priority_queue<T,std::vector<T>,std::function<bool ( T,T ) >>
    template <typename T,typename Queue=std::deque<T>>
    class blocking_queue {
    private:
        std::mutex d_mutex;
        std::condition_variable d_condition;
        Queue d_queue;
    public:
        blocking_queue ( std::function<bool ( T,T ) > f=[] ( T , T ) {return true;} )
            :d_queue ( f ) {}
        void push ( T value ) {
            std::unique_lock<std::mutex> lock ( d_mutex );
            d_queue.push_front ( value );
            d_condition.notify_one();
        }
        T pop() {
            std::unique_lock<std::mutex> lock ( d_mutex );
            d_condition.wait ( lock, [=] { return !d_queue.empty(); } );
            return vstd::pop ( d_queue );
        }
    };
}
