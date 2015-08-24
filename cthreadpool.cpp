#include "CThreadPool.h"

void CThreadPool::run ( std::function<void () > target ) {
    run ( new CRunnableWrapper ( target ) );
}

void CThreadPool::run ( QRunnable *runnable ) {
    if ( !pool.tryStart ( runnable ) ) {
        addThreads ( 1 );
        run ( runnable );
    }
}

CThreadPool::CThreadPool() {

}

void CThreadPool::addThreads ( int num ) {
    pool.setMaxThreadCount ( pool.maxThreadCount()+num );
    qDebug() <<"Max thread count:"<< pool.maxThreadCount() <<"\n";
}

CThreadPool *CThreadPool::instance() {
    static CThreadPool self;
    return &self;
}

void CThreadPool::CRunnableWrapper::run() {
    target();
}

CThreadPool::CRunnableWrapper::CRunnableWrapper ( std::function<void () > target ) :target ( target ) {

}
