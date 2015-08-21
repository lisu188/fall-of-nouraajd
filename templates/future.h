#pragma once

#include "templates/util.h"
#include "templates/thread.h"

namespace vstd {
    template<typename F,
             typename return_type=typename function_traits<F>::return_type,
             typename argument_type=typename function_traits<F>::template arg<0>::type>
    class ccall:public std::enable_shared_from_this<ccall<return_type,argument_type>> {

        volatile bool completed=false;
        std::condition_variable condition;
        std::mutex mutex;
        return_type* result=_new<return_type>();
        argument_type* argument=_new<argument_type>();

        template<typename X>
        X* _new ( typename vstd::disable_if<vstd::is_same<X,void>::value>::type * = 0 ) {
            return new X();
        }
        template<typename X>
        X* _new ( typename vstd::enable_if<vstd::is_same<X,void>::value>::type * = 0 ) {
            return nullptr;
        }
        template<typename X>
        void _delete ( typename vstd::disable_if<vstd::is_same<X,void>::value>::type * = 0 ) {
            delete result;
        }
        template<typename X>
        void _delete ( typename vstd::enable_if<vstd::is_same<X,void>::value>::type * = 0 ) {

        }

    public:
        ccall ( F func ,std::function<void ( std::function<void() > ) > caller ) :_target ( func ),_caller ( caller ) {

        }

        template<typename X=argument_type>
        argument_type getArgument ( typename vstd::disable_if<vstd::is_same<X,void>::value>::type * = 0 ) {
            return *argument;
        }

        template<typename X=argument_type>
        void *getArgument ( typename vstd::enable_if<vstd::is_same<X,void>::value>::type * = 0 ) {
            return nullptr;
        }

        template<typename X=argument_type>
        void setArgument ( X x,typename vstd::disable_if<vstd::is_same<X,void>::value>::type * = 0 ) {
            *argument=x;
        }

        template<typename X=argument_type>
        void setArgument ( void * x,typename vstd::enable_if<vstd::is_same<X,void>::value>::type * = 0 ) {
            argument=nullptr;
        }

        ~ccall() {
            _delete();
        }

        template<typename X=return_type>
        void setResult ( X t ,typename vstd::disable_if<vstd::is_same<X,void>::value>::type * = 0 ) {
            std::unique_lock<std::mutex> ( mutex );
            *result=t;
            completed=true;
            condition.notify_all();
        }
        template<typename X=return_type>
        X getResult ( typename vstd::disable_if<vstd::is_same<X,void>::value>::type * = 0 ) {
            std::unique_lock<std::mutex> ( mutex );
            condition.wait ( mutex,[=]() {return completed;} );
            return *result;
        }
        template<typename X=return_type>
        void setResult ( typename vstd::enable_if<vstd::is_same<X,void>::value>::type * = 0 ) {
            std::unique_lock<std::mutex> ( mutex );
            completed=true;
            condition.notify_all();
        }
        template<typename X=return_type>
        X getResult ( typename vstd::enable_if<vstd::is_same<X,void>::value>::type * = 0 ) {
            std::unique_lock<std::mutex> ( mutex );
            condition.wait ( mutex,[=]() {return completed;} );
        }

        void call() {
            auto self=this->shared_from_this();
            vstd::call ( _caller,[self] ( ) {
                self->setResult ( vstd::call ( self->get_target() ) );
            } );
        }

        bool isCompleted() {
            std::unique_lock<std::mutex> ( mutex );
            return completed;
        }

    private:
        template<typename G,typename X=return_type,typename Y=argument_type>
        auto normalize ( G f,
                         typename vstd::enable_if<std::is_void<X>::value>::type * = 0,
                         typename vstd::enable_if<std::is_void<Y>::value>::type * = 0 ) {
            return [f] ( void * x )->void* {
                f();
                return nullptr;
            };
        }

        template<typename G,typename X=return_type,typename Y=argument_type>
        auto normalize ( G f,
                         typename vstd::disable_if<std::is_void<X>::value>::type * = 0,
                         typename vstd::enable_if<std::is_void<Y>::value>::type * = 0 ) {
            return [f] ( void * x ) {
                return f();
            };
        }

        template<typename G,typename X=return_type,typename Y=argument_type>
        auto normalize ( G f,
                         typename vstd::enable_if<std::is_void<X>::value>::type * = 0,
                         typename vstd::disable_if<std::is_void<Y>::value>::type * = 0 ) {
            return [f] ( argument_type t )->void* {
                f ( t );
                return nullptr;
            };
        }

        template<typename G,typename X=return_type,typename Y=argument_type>
        auto normalize ( G f,
                         typename vstd::disable_if<std::is_void<X>::value>::type * = 0,
                         typename vstd::disable_if<std::is_void<Y>::value>::type * = 0 ) {
            return f;
        }

        std::function<return_type() > get_target() {
            return vstd::bind ( normalize ( _target ),getArgument() );
        }

        F _target;
        std::function<void ( std::function<void() > ) > _caller;
    };

    class request_processor {
    public:
        request_processor() :_thread ( std::mem_fn ( &request_processor::process ),this ) {

        }
        template<typename F,typename... Args>
        void post ( F f,Args... args ) {
            _queue.push ( vstd::bind ( f,args... ) );
        }
        void start() {
            post ( [=]() {
                _active=true;
            } );
        }
        void stop() {
            post ( [=]() {
                _active=false;
            } );
        }
        ~request_processor() {
            stop();
            _thread.join();
        }
    private:
        void process() {
            do {
                vstd::call ( _queue.pop() );
            } while ( _active );
        }
        vstd::blocking_queue<std::function<void() >> _queue;
        std::thread _thread;
        bool _active=true;
    };

    namespace detail {
        template<typename func>
        std::shared_ptr<ccall<func>> make_async ( func f ) {
            return std::make_shared<ccall<func>> ( f,call_async<func> ) ;
        }

        template<typename func>
        std::shared_ptr<ccall<func>> make_later ( func f ) {
            return std::make_shared<ccall<func>> ( f,call_later<func> ) ;
        }
    }

    template<typename F=std::function<void() >,
             typename return_type=typename function_traits<F>::return_type,
             typename argument_type=typename function_traits<F>::template arg<0>::type>
    class future : public std::enable_shared_from_this<future<F,return_type,argument_type>> {
        friend class __gnu_cxx::new_allocator<future<F,return_type,argument_type>>;
    public:
        //TODO: replace with method aggregating futures
        template<typename Range,typename Func>
        static void when_all_done ( Range range,Func func,typename vstd::enable_if<vstd::is_pure_range<Range>::value>::type* =0 ) {
            for ( auto a:collect ( range ) ) {
                a->get();
            }
            call_later ( func );
        }

        template<typename Range,typename Func>
        static void when_all_done ( Range range,Func func,typename vstd::disable_if<vstd::is_pure_range<Range>::value>::type* =0 ) {
            for ( auto a: range  ) {
                a->get();
            }
            call_later ( func );
        }

        auto get ( ) {
            vstd::wait_until ( [this]() {
                return _call->isCompleted();
            } );
            return _call->getResult();
        }

        //TODO: rethink this and move constructing static functions outside
    private:
        future ( std::shared_ptr<ccall<F>> call,std::shared_ptr<request_processor> processor ) :
            _call ( call ),
            _processor ( processor ) {

        }
        future ( std::shared_ptr<ccall<F>> call ) :
            _call ( call ),
            _processor ( std::make_shared<request_processor>() ) {
            _processor->post ( vstd::bind ( [] ( std::shared_ptr<ccall<F>> c ) {
                c->call();
            },_call ) );
        }
        template <typename G>
        auto thenLater ( G g ) {
            return chain_call ( detail::make_later ( g ) );
        }
        template <typename G>
        auto thenAsync ( G g ) {
            return chain_call ( detail::make_async ( g ) );
        }
    private:
        template<typename G>
        auto chain_call ( std::shared_ptr<G> _new_call ) {
            auto _self=this->shared_from_this();
            _processor->post ( [_self,_new_call]() {
                auto arg = _self->_call->getResult();
                _new_call->setArgument ( arg );
                _new_call->call();
            } );
            return std::make_shared<future<G>> ( _new_call,_processor );
        }

        const std::shared_ptr<ccall<F>> _call;
        const std::shared_ptr<request_processor> _processor;
    public:
        template<typename Func>
        static auto later ( Func f ) {
            return std::make_shared<future<Func>> ( detail::make_later ( f ) );
        }

        template<typename Func>
        static auto async ( Func f ) {
            return std::make_shared<future<Func>> ( detail::make_async ( f ) );
        }

        template<typename X>
        future ( future<X> other ) {
            _call=other._call;
            _processor=other._processor;
        }
    };

    template<typename F,typename Arg=typename vstd::function_traits<F>::template arg<0>::type>
    auto wrap_later ( F f ) {
        return [f] ( Arg a ) {
            return future<>::later ( vstd::bind ( f,a ) );
        };
    }

    template<typename F,typename Arg=typename vstd::function_traits<F>::template arg<0>::type>
    auto wrap_async ( F f ) {
        return [f] ( Arg a ) {
            return future<>::async ( vstd::bind ( f,a ) );
        };
    }
}
