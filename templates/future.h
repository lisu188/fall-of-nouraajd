#pragma once

#include "templates/util.h"
#include "templates/thread.h"

namespace vstd {
    template<typename T>
    class ccall:public std::enable_shared_from_this<ccall<T>> {
    public:
        virtual void call() = 0;
        void setResult ( T t ) {
            result=t;
            completed=true;
        }
        T getResult() {
            return result;
        }
        bool isCompleted() {
            return completed;
        }
    private:
        bool completed=false;
        T result;
    };

    template<>
    class ccall<void>:public std::enable_shared_from_this<ccall<void>> {
    public:
        virtual void call() = 0;
        void setCompleted ( ) {
            completed=true;
        }
        bool isCompleted() {
            return completed;
        }
    private:
        bool completed=false;
    };

    template<typename F>
    class clatercall:public ccall<typename vstd::function_traits<F>::return_type> {
    public:
        clatercall ( F target ) :target ( target ) {}
        void call() override final {
            _call();
        }
    private:
        template<typename T=typename vstd::function_traits<F>::return_type>
        force_inline void _call ( typename vstd::enable_if<std::is_same<T,void>::value>::type* =0 ) {
            auto self=this->shared_from_this();
            call_later ( [self] ( F target ) {
                target();
                self->setCompleted();
            } ,target );
        }
        template<typename T=typename vstd::function_traits<F>::return_type>
        force_inline void _call ( typename vstd::disable_if<std::is_same<T,void>::value>::type* =0 ) {
            auto self=this->shared_from_this();
            call_later ( [self] ( F target ) {
                self->setResult ( target() );
            } ,target );
        }
        F target;
    };

    template<typename F>
    class casynccall:public ccall<typename vstd::function_traits<F>::return_type> {
    public:
        casynccall ( F target ) :target ( target ) {}
        void call() override final {
            _call();
        }
    private:
        template<typename T=typename vstd::function_traits<F>::return_type>
        force_inline void _call ( typename vstd::enable_if<std::is_same<T,void>::value>::type* =0 ) {
            auto self=this->shared_from_this();
            call_async ( target,[self] (  ) {
                self->setCompleted (  );
            } );
        }
        template<typename T=typename vstd::function_traits<F>::return_type>
        force_inline void _call ( typename vstd::disable_if<std::is_same<T,void>::value>::type* =0 ) {
            auto self=this->shared_from_this();
            call_async ( target,[self] ( typename vstd::function_traits<F>::return_type value ) {
                self->setResult ( value );
            } );
        }
        F target;
    };

    template<typename T=void>
    class future : public std::enable_shared_from_this<future<T>> {
        friend class __gnu_cxx::new_allocator<future<T>>;
    public:
        template<typename F>
        static auto later ( F f ) {
            return std::make_shared<future<
                   typename vstd::function_traits<F>::return_type>> (
                       std::shared_ptr<clatercall<F>> ( new clatercall<F> ( f ) ) )->start();
        }
        template<typename F>
        static auto async ( F f ) {
            return std::make_shared<future<
                   typename vstd::function_traits<F>::return_type>> (
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

        template<typename U=T>
        U get ( typename vstd::disable_if<std::is_same<U,void>::value>::type* =0 ) {
            assert_main_thread();
            vstd::wait_until ( [this]() {
                return call->isCompleted();
            } );
            return call->getResult();
        }
        template<typename U=T>
        U get ( typename vstd::enable_if<std::is_same<U,void>::value>::type* =0 ) {
            assert_main_thread();
            vstd::wait_until ( [this]() {
                return call->isCompleted();
            } );
        }
        //TODO: rethink this and move constructing static functions outside
    public:
        future ( std::shared_ptr<ccall<T>> call ) :call ( call ) {
            assert_main_thread();
        }
        std::shared_ptr<future<T>> start() {
            call->call();
            return this->shared_from_this();
        }
        std::shared_ptr<ccall<T>> call;
    };
}
