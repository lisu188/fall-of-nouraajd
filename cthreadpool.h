#pragma once
#include "CGlobal.h"

class CThreadPool {
    class CRunnableWrapper:public QRunnable {
        friend class CThreadPool;
    public:
        void run() override final;
    private:
        CRunnableWrapper ( std::function<void() > target );
        std::function<void() > target;
    };
public:
    static CThreadPool *instance();
    void run ( std::function<void() > target );
    void run ( QRunnable *runnable );
private:
    CThreadPool();
    void addThreads ( int num );
    QThreadPool pool;
};

