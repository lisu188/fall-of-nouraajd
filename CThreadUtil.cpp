#include "CThreadUtil.h"

CLaterCall::CLaterCall ( std::function<void () > target ) :target ( target ) {
    this->moveToThread(QApplication::instance()->thread());
}

void CLaterCall::run() {
    QMetaObject::invokeMethod ( this,"call",Qt::ConnectionType::BlockingQueuedConnection );
}

void CLaterCall::call() {
    target();
}
