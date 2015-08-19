#pragma once
#include "CGlobal.h"
#include "CUtil.h"
#include "templates/traits.h"
#include "templates/util.h"
#include "CDefines.h"

namespace vstd  {
    template <typename Function,typename... Arguments>
    force_inline void call_later ( Function target,Arguments... params ) {
        QThreadPool::globalInstance()->start ( new CInvokeLater ( vstd::bind ( target,params... ) ) );
    }

    template <typename Predicate,typename Function>
    force_inline void call_when ( Predicate pred,Function func ) {
        if ( pred() ) {
            func();
        } else {
            call_later ( [pred,func]() {
                call_when ( pred,func );
            } );
        }
    }

    template <typename Predicate>
    force_inline void wait_until ( Predicate pred ) {
        while ( !pred() ) {
            QApplication::processEvents ( QEventLoop::WaitForMoreEvents );
        }
        //wake up call for other waiting functions
        QApplication::postEvent ( QApplication::instance(),
                                  new QEvent ( QEvent::Type::None ) );

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
}
