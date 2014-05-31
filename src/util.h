#ifndef UTIL_H
#define UTIL_H
#include <sstream>
#include <QVariant>
#include <QRunnable>
#include <functional>
namespace util
{
template < typename T > std::string to_string(const T& n)
{
    std::ostringstream stm ;
    stm << n ;
    return stm.str() ;
}
}

class GameTask : public QObject,public QRunnable{
    Q_OBJECT
public:
    GameTask(std::function<void()> task){
        this->task=task;
    }

    void run(){
        Q_EMIT started();
        task();
        Q_EMIT finished();
    }

    Q_SIGNAL void started();
    Q_SIGNAL void finished();
private:
    std::function<void()> task;
};
#endif // UTIL_H
