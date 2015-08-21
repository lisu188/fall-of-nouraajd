#pragma once

#include "templates/util.h"
#include "templates/thread.h"

namespace vstd {
    template<typename F,
             typename T=typename function_traits<F>::return_type,
             typename U=typename function_traits<F>::template arg<0>::type>
    class ccall:public std::enable_shared_from_this<ccall<T,U>> {
        typedef T return_type;
        typedef U argument_type;

        volatile bool completed=false;
        std::condition_variable condition;
        std::mutex mutex;
        T* result=_new<T>();
        U* argument=_new<U>();

        ccall(F func):_target(func){

        }

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

        template<typename X=U>
        U getArgument (typename vstd::disable_if<vstd::is_same<X,void>::value>::type * = 0 ) {
            return *argument;
        }

        template<typename X=U>
        void *getArgument (typename vstd::enable_if<vstd::is_same<X,void>::value>::type * = 0 ) {
            return nullptr;
        }

        template<typename X=U>
        void setArgument (X x,typename vstd::disable_if<vstd::is_same<X,void>::value>::type * = 0 ) {
            *argument=x;
        }

        template<typename X=U>
        void setArgument (void * x,typename vstd::enable_if<vstd::is_same<X,void>::value>::type * = 0 ) {
            argument=nullptr;
        }

        virtual void call ( ) = 0;
        virtual ~ccall() {
            _delete();
        }

        template<typename X=T>
        void setResult ( X t ,typename vstd::disable_if<vstd::is_same<X,void>::value>::type * = 0 ) {
            std::unique_lock<std::mutex> ( mutex );
            *result=t;
            completed=true;
            condition.notify_all();
        }
        template<typename X=T>
        X getResult ( typename vstd::disable_if<vstd::is_same<X,void>::value>::type * = 0 ) {
            std::unique_lock<std::mutex> ( mutex );
            condition.wait ( mutex,[=]() {return completed;} );
            return *result;
        }
        template<typename X=T>
        void setResult ( typename vstd::enable_if<vstd::is_same<X,void>::value>::type * = 0 ) {
            std::unique_lock<std::mutex> ( mutex );
            completed=true;
            condition.notify_all();
        }
        template<typename X=T>
        X getResult ( typename vstd::enable_if<vstd::is_same<X,void>::value>::type * = 0 ) {
            std::unique_lock<std::mutex> ( mutex );
            condition.wait ( mutex,[=]() {return completed;} );
        }

        bool isCompleted() {
            std::unique_lock<std::mutex> ( mutex );
            return completed;
        }

        template<typename F,typename X=return_type,Y=argument_type>
        auto normalize(F f,
                              vstd::enable_if<std::is_void<X>::value>::type * = 0
                                ,vstd::enable_if<std::is_void<Y>::value>::type * = 0){
            return [f](void * x)->void*{
                f();
                return nullptr;
            };
        }

        template<typename F,typename X=return_type,Y=argument_type>
        auto normalize(F f,
                              vstd::disable_if<std::is_void<X>::value>::type * = 0
                                ,vstd::enable_if<std::is_void<Y>::value>::type * = 0){
            return [f](void * x){
                return f();
            };
        }

        template<typename F,typename X=return_type,Y=argument_type>
        auto normalize(F f,
                              vstd::enable_if<std::is_void<X>::value>::type * = 0
                                ,vstd::disable_if<std::is_void<Y>::value>::type * = 0){
            return [f](argument_type t)->void*{
                f(t);
                return nullptr;
            };
        }

        template<typename F,typename X=return_type,Y=argument_type>
        auto normalize(F f,
                              vstd::disable_if<std::is_void<X>::value>::type * = 0
                                ,vstd::disable_if<std::is_void<Y>::value>::type * = 0){
            return f;
        }

        std::function<return_type()> get_target(){
            return vstd::bind(normalize(_target),getArgument());
        }

        F _target;
    };

    template<typename F>
    class clatercall:public ccall<typename vstd::function_traits<F>::return_type,
        typename vstd::function_traits<F>::template arg<0>::type> {
    public:

        clatercall ( F target ):_target(target){

        }

    void call() override final {
        auto self=this->shared_from_this();
        call_later ( [self] ( ) {
            self->setResult ( vstd::call(self->get_target()) );
        } );
    }
                                                      };
    template<typename F>
    class casynccall:public ccall<typename vstd::function_traits<F>::return_type,
        typename vstd::function_traits<F>::template arg<0>::type> {
        public:
    casynccall ( F target ) : target ( target ) {}

    void call() override final {
        auto self=this->shared_from_this();
        call_later ( [self] ( ) {
            self->setResult ( vstd::call(self->get_target()) );
        } );
    }
                                                      };

    template<typename T=void,typename U=void>
    class future : public std::enable_shared_from_this<future<T,U>> {
        friend class __gnu_cxx::new_allocator<future<T,U>>;
    public:
        template<typename F>
        static auto later ( F f ) {
            return std::make_shared<future<
                   typename vstd::function_traits<F>::return_type,
                   typename vstd::function_traits<F>::template arg<0>::type>> (
                               std::shared_ptr<clatercall<F>> ( new clatercall<F> ( f ) ) )->start();
        }
        template<typename F>
        static auto async ( F f ) {
            return std::make_shared<future<
                   typename vstd::function_traits<F>::return_type,
                   typename vstd::function_traits<F>::template arg<0>::type>> (
                               std::shared_ptr<casynccall<F>> ( new casynccall<F> ( f ) ) )->start();
        }

        template<typename F,typename Arg=typename vstd::function_traits<F>::template arg<0>::type>
        static auto wrap_later ( F f ) {
            return [f] ( Arg a ) {
                return later ( vstd::bind ( f,a ) );
            };
        }
        template<typename F,typename Arg=typename vstd::function_traits<F>::template arg<0>::type>
        static auto wrap_async ( F f ) {
            return [f] ( Arg a ) {
                return async ( vstd::bind ( f,a ) );
            };
        }

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

        template<typename F,typename SelfReturn=T,typename FuncReturn=typename function_traits<F>::return_type>
        auto thenLater ( F f,
                         typename vstd::enable_if<!vstd::is_same<SelfReturn,void>::value>::type* =0,
                         typename vstd::enable_if<!vstd::is_same<FuncReturn,void>::value>::type* =0 ) {
            auto self=this->shared_from_this();
            return later ( [self,f]() {
                return later ( vstd::bind ( f,self->get() ) )->get();
            } );
        }
        template<typename F,typename SelfReturn=T,typename FuncReturn=typename function_traits<F>::return_type>
        auto thenLater ( F f,
                         typename vstd::enable_if<vstd::is_same<SelfReturn,void>::value>::type* =0,
                         typename vstd::enable_if<!vstd::is_same<FuncReturn,void>::value>::type* =0 ) {
            auto self=this->shared_from_this();
            return later ( [self,f]() {
                self->get();
                return later ( f )->get();
            } );
        }
        template<typename F,typename SelfReturn=T,typename FuncReturn=typename function_traits<F>::return_type>
        auto thenLater ( F f,
                         typename vstd::enable_if<!vstd::is_same<SelfReturn,void>::value>::type* =0,
                         typename vstd::enable_if<vstd::is_same<FuncReturn,void>::value>::type* =0 ) {
            auto self=this->shared_from_this();
            return later ( [self,f]() {
                later ( vstd::bind ( f,self->get() ) )->get();
            } );
        }
        template<typename F,typename SelfReturn=T,typename FuncReturn=typename function_traits<F>::return_type>
        auto thenLater ( F f,
                         typename vstd::enable_if<vstd::is_same<SelfReturn,void>::value>::type* =0,
                         typename vstd::enable_if<vstd::is_same<FuncReturn,void>::value>::type* =0 ) {
            auto self=this->shared_from_this();
            return later ( [self,f]() {
                self->get();
                later ( f )->get();
            } );
        }

        template<typename F,typename SelfReturn=T,typename FuncReturn=typename function_traits<F>::return_type>
        auto thenAsync ( F f,
                         typename vstd::enable_if<!vstd::is_same<SelfReturn,void>::value>::type* =0,
                         typename vstd::enable_if<!vstd::is_same<FuncReturn,void>::value>::type* =0 ) {
            auto self=this->shared_from_this();
            return async ( [self,f]() {
                return async ( vstd::bind ( f,self->get() ) )->get();
            } );
        }
        template<typename F,typename SelfReturn=T,typename FuncReturn=typename function_traits<F>::return_type>
        auto thenAsync ( F f,
                         typename vstd::enable_if<vstd::is_same<SelfReturn,void>::value>::type* =0,
                         typename vstd::enable_if<!vstd::is_same<FuncReturn,void>::value>::type* =0 ) {
            auto self=this->shared_from_this();
            return async ( [self,f]() {
                self->get();
                return async ( f )->get();
            } );
        }
        template<typename F,typename SelfReturn=T,typename FuncReturn=typename function_traits<F>::return_type>
        auto thenAsync ( F f,
                         typename vstd::enable_if<!vstd::is_same<SelfReturn,void>::value>::type* =0,
                         typename vstd::enable_if<vstd::is_same<FuncReturn,void>::value>::type* =0 ) {
            auto self=this->shared_from_this();
            return async ( [self,f]() {
                async ( vstd::bind ( f,self->get() ) )->get();
            } );
        }
        template<typename F,typename SelfReturn=T,typename FuncReturn=typename function_traits<F>::return_type>
        auto thenAsync ( F f,
                         typename vstd::enable_if<vstd::is_same<SelfReturn,void>::value>::type* =0,
                         typename vstd::enable_if<vstd::is_same<FuncReturn,void>::value>::type* =0 ) {
            auto self=this->shared_from_this();
            return async ( [self,f]() {
                self->get();
                async ( f )->get();
            } );
        }

        template<typename X=T>
        X get ( typename vstd::disable_if<std::is_same<X,void>::value>::type* =0 ) {
            vstd::wait_until ( [this]() {
                return call->isCompleted();
            } );
            return call->getResult();
        }
        template<typename X=T>
        X get ( typename vstd::enable_if<std::is_same<X,void>::value>::type* =0 ) {
            vstd::wait_until ( [this]() {
                return call->isCompleted();
            } );
        }
        //TODO: rethink this and move constructing static functions outside
    public:
        future ( std::shared_ptr<ccall<T,U>> call ) : call ( call ) {
            call->call();
        }

        std::shared_ptr<ccall<T,U>> call;
        std::shared_ptr<request_processor> _processor;
    };

    class request_processor{
    public:
        request_processor():_thread(std::mem_fn(process,this)){

        }
        template<typename F,typename... Args>
        void post(F f,Args... args){
            _queue.push(vstd::bind(f,args...));
        }
        void start(){
            post([=](){
                _active=true;
            });
        }
        void stop(){
            post([=](){
                _active=false;
            });
        }
        ~request_processor(){
            stop();
            _thread.join();
        }
    private:
        void process(){
            do{
                vstd::call(_queue.pop());
            }while(_active);
        }
        vstd::blocking_queue<std::function<void()>> _queue;
        std::thread _thread;
        bool _active=true;
    };
}
