#pragma once
#include "CGlobal.h"
#include "CUtil.h"
#include "templates/traits.h"
#include "templates/util.h"
#include "CDefines.h"
#include "CThreadPool.h"

namespace vstd  {
    template <typename Function,typename... Arguments>
    force_inline void call_later ( Function target,Arguments... args ) {
        QApplication::postEvent ( CInvocationHandler::instance(),
                                  new CInvocationEvent ( vstd::bind ( target,args... ) ) );
    }

    template <typename Function,typename... Arguments>
    force_inline void call_async ( Function target ,Arguments... args ) {
        CThreadPool::instance()->run ( vstd::bind ( target,args... ) );
    }

    template <typename Function,typename... Arguments>
    force_inline void call_later_block ( Function target,Arguments... args ) {
        QApplication::sendEvent ( CInvocationHandler::instance(),
                                  new CInvocationEvent ( vstd::bind ( target,args... ) ) );
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
        auto bind=vstd::bind ( func,params... );
        call_later ( [pred,bind]() {
            wait_until ( pred );
            call_later ( bind );
        } );
    }
}
