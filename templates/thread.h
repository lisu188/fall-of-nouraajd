#pragma once
#include "CGlobal.h"
#include "CUtil.h"
#include "templates/traits.h"
#include "templates/util.h"
#include "CDefines.h"
#include "CThreadPool.h"

namespace vstd  {
    template <typename Function,typename... Arguments>
    force_inline void call_later ( Function target,Arguments... params ) {
        QApplication::postEvent ( CInvocationHandler::instance(),
                                  new CInvocationEvent ( vstd::bind ( target,params... ) ) );
    }

    template <typename Function,typename... Arguments>
    force_inline void call_later_block ( Function target,Arguments... params ) {
        QApplication::sendEvent ( CInvocationHandler::instance(),
                                  new CInvocationEvent ( vstd::bind ( target,params... ) ) );
    }

    template <typename Predicate>
    force_inline void wait_until ( Predicate pred ) {
        call_later_block ( [pred]() {
            while ( !pred() ) {
                QApplication::processEvents ( QEventLoop::WaitForMoreEvents );
            }
        } );
    }

    template <typename Predicate,typename Function,typename... Arguments>
    force_inline void call_when ( Predicate pred,Function func,Arguments... params ) {
        call_later ( [pred,func,params...]() {
            wait_until ( pred );
            call_later ( func,params... );
        } );
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
    force_inline void call_async ( Function target,Callback callback=[] ( typename vstd::function_traits<Function>::return_type x ) {} ) {
        CThreadPool::instance()->run ( new CAsyncCall<Function,Callback> ( target,callback ) );
    }
}
