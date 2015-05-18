#include "CThreadUtil.h"

CLaterCall::CLaterCall(std::function<void ()> target) :target ( target ) {

}

void CLaterCall::run(){
    QMetaObject::invokeMethod ( this,"call",Qt::ConnectionType::BlockingQueuedConnection );
}

void CLaterCall::call(){
    target();
}

void CThreadUtil::call_later(std::function<void ()> target) {
    QThreadPool::globalInstance()->start( new CLaterCall (target));
}
