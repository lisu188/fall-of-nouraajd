#pragma once
#include "CGlobal.h"
#include "CUtil.h"
#include "templates/traits.h"
#include "templates/util.h"
#include "CDefines.h"

namespace vstd  {

    template <typename Predicate>
    force_inline void wait_until ( Predicate pred ) {
        while ( !pred() ) {
            QApplication::processEvents ( QEventLoop::WaitForMoreEvents );
        }
    }

    template <typename Function,typename... Arguments>
    force_inline void call_later ( Function target,Arguments... params ) {
        QThreadPool::globalInstance()->start ( new CInvokeLater ( vstd::bind ( target,params... ) ) );
    }

    template <typename Function,typename... Arguments>
    force_inline void call_later_wait ( Function target,Arguments... params ) {
        std::make_shared<CInvokeLater> ( vstd::bind ( target,params... ) )->run();
    }

    template <typename Function,typename Callback>
    class CAsyncCall:public QRunnable {
    public:
        CAsyncCall ( Function target,Callback callback ) :target ( target ),callback ( callback ) {}
        void run() override {
            _run();
        }
    private:
        template<typename T=typename vstd::function_traits<Function>::return_type>
        force_inline void _run ( typename vstd::enable_if<std::is_same<T,void>::value>::type* =0 ) {
            target();
            call_later ( [this] ( Callback cb ) {
                cb (  );
            },callback );
        }
        template<typename T=typename vstd::function_traits<Function>::return_type>
        force_inline void _run ( typename vstd::disable_if<std::is_same<T,void>::value>::type* =0 ) {
            call_later ( [this] ( typename function_traits<Function>::return_type result,Callback cb ) {
                cb ( result );
            },target(),callback );
        }
        Function target;
        Callback callback;
    };

    template <typename Function,typename Callback>
    force_inline void call_async ( Function target,Callback callback=[] ( vstd::function_traits<Function> ) {} ) {
        QThreadPool::globalInstance()->start ( new CAsyncCall<Function,Callback> ( target,callback ) );
    }

    template <typename Collection,typename Callback,typename Function>
    force_inline void invoke_all ( Collection all, Function target,Callback callback=[] ( typename vstd::function_traits<Function>::result_type ) {},std::function<void() > end_callback=[]() {} ) {
        typedef typename Collection::value_type Result;
        typedef typename vstd::function_traits<Function>::return_type Return;
        call_later ( [all,target,callback,end_callback]() {
            std::shared_ptr<int> called=std::make_shared<int> ( all.size() );
            for ( Result t:all ) {
                std::function<Return() > real_function=vstd::bind ( target,t );
                std::function<void ( Return ) > real_callback=[called,callback,end_callback] ( Return r ) {
                    callback ( r );
                    if ( -- ( *called ) <=0 ) {
                        call_later ( end_callback );
                    }
                };
                call_async ( real_function,real_callback );
            }
        } );
    }
}
