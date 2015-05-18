#pragma once
#include <QThreadPool>
#include <functional>
#include "Util.h"

class CLaterCall:public QObject,public QRunnable {
    Q_OBJECT
    friend class CThreadUtil;
private:
    CLaterCall ( std::function<void () > target );
    void run() override;
    Q_INVOKABLE void call();
    std::function<void() > target;
};

class CThreadUtil  {
public:
    template <typename Function,typename... Arguments>
    static void call_later ( Function target,Arguments... params ) {
        QThreadPool::globalInstance()->start ( new CLaterCall ( std::bind ( target,params... ) ) );
    }
    template <typename Function,typename Callback>
    static void call_async ( Function target,Callback callback=[] ( function_traits<Function> ) {} ) {
        QThreadPool::globalInstance()->start ( new CAsyncCall<Function,Callback> ( target,callback ) );
    }
    template <typename Collection,typename Callback,typename Function>
    static void invoke_all ( Collection all, Function target,Callback callback=[] ( typename function_traits<Function>::result_type ) {},std::function<void() > end_callback=[]() {} ) {
        typedef typename Collection::value_type Result;
        typedef typename function_traits<Function>::result_type Return;
        call_later ( [all,target,callback,end_callback]() {
            int *called=new int ( all.size() );
            for ( Result t:all ) {
                std::function<Return() > real_function=std::bind ( target,t );
                std::function<void ( Return ) > real_callback=[called,callback,end_callback] ( Return r ) {
                    callback ( r );
                    if ( -- ( *called ) ) {
                        delete called;
                        call_later ( end_callback );
                    }
                };
                call_async ( real_function,real_callback );
            }
        } );
    }
private:
    template <typename Function,typename Callback>
    class CAsyncCall:public QRunnable {
        friend class CThreadUtil;
    private:
        CAsyncCall ( Function target,Callback callback ) :target ( target ),callback ( callback ) {}
        void run() override {
            call_later ( [this] ( typename function_traits<Function>::result_type result ) {
                callback ( result );
            },target() );
        }
        Function target;
        Callback callback;
    };
};


