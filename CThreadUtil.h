#pragma once
#include <QThreadPool>
#include <functional>

class CLaterCall:public QObject,public QRunnable{
    Q_OBJECT
    friend class CThreadUtil;
private:
    CLaterCall(std::function<void ()> target);
    void run() override;
    Q_INVOKABLE void call();
    std::function<void() > target;
};

class CThreadUtil  {
public:
    static void call_later ( std::function<void()> target );
    template <typename T>
    static void call_async ( std::function<T()> target,std::function<void(T) > callback){
        QThreadPool::globalInstance()->start( new CAsyncCall<T>(target,callback));
    }
private:
    template<typename T>
    class CAsyncCall:public QRunnable{
        friend class CThreadUtil;
    private:
        CAsyncCall( std::function<T()> target,std::function<void(T) > callback):target(target),callback(callback){}
        void run() override{
            T result=target();
            call_later([this,result](){
                    callback(result);
            });
        }
        std::function<T() > target;
        std::function<void(T) > callback;
    };
};


