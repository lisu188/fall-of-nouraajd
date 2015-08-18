#pragma once

#include "templates/thread.h"

namespace vstd {
    template<typename T>
    class ccall:public std::enable_shared_from_this<ccall<T>> {
    public:
        virtual void call() = 0;
        void setResult ( T t ) {
            result=std::make_shared<T> ( t );
        }
        T getResult() {
            return *result;
        }
        bool isCompleted() {
            return result.operator bool();
        }
    private:
        std::shared_ptr<T> result;
    };

    template<typename F>
    class clatercall:public ccall<typename vstd::function_traits<F>::return_type> {
    public:
        clatercall ( F target ) :target ( target ) {}
        void call() override final {
            auto self=this->shared_from_this();
            call_later ( [self] ( F target ) {
                self->setResult ( target() );
            } ,target );
        }
    private:
        F target;
    };

    template<typename F>
    class casynccall:public ccall<typename vstd::function_traits<F>::return_type> {
    public:
        casynccall ( F target ) :target ( target ) {}
        void call() override final {
            auto self=this->shared_from_this();
            call_async ( target,[self] ( typename vstd::function_traits<F>::return_type value ) {
                self->setResult ( value );
            } );
        }
    private:
        F target;
    };

    template<typename T>
    class future : public std::enable_shared_from_this<future<T>> {
        friend class __gnu_cxx::new_allocator<future<T>>;
    public:
        template<typename F>
        static auto later ( F f ) {
            return std::make_shared<future<T>> ( std::make_shared<clatercall<F>> ( f ) )->start();
        }
        template<typename F>
        static auto async ( F f ) {
            return std::make_shared<future<T>> ( std::make_shared<casynccall<F>> ( f ) )->start();
        }

        template<typename F>
        auto thenLater ( F f ) {
            auto self=this->shared_from_this();
            return later ( [self,f]() {
                return later ( std::bind ( f,self->get() ) )->get();
            } );
        }
        template<typename F>
        auto thenAsync ( F f ) {
            auto self=this->shared_from_this();
            return async ( [self,f]() {
                return async ( std::bind ( f,self->get() ) )->get();
            } );
        }

        T get() {
            vstd::call_later_wait ( [this]() {
                vstd::wait_until ( [this]() {
                    return call->isCompleted();
                } );
            } );
            return call->getResult();
        }
    private:
        future ( std::shared_ptr<ccall<T>> call ) :call ( call ) {

        }
        std::shared_ptr<future<T>> start() {
            call->call();
            return this->shared_from_this();
        }
        std::shared_ptr<ccall<T>> call;
    };
}
