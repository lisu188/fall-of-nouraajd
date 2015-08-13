#pragma once

namespace vstd {
    template<typename T,typename U=int>
    U fail_if ( T arg,QString msg ) {
        if ( arg ) {
            qFatal ( msg.toStdString().c_str() );
        }
        return U();
    }

    template<typename T=int>
    T fail ( QString msg ) {
        return fail_if<bool,T> ( true,msg );
    }

    template <typename T>
    T not_null ( T t,QString msg="" ) {
        if ( t ) {
            return t;
        }
        return fail<T> ( msg );
    }
}
