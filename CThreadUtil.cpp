#include "CThreadUtil.h"

CLaterCall::CLaterCall ( std::function<void () > target ) :target ( target ) {

}

void CLaterCall::run() {
    QMetaObject::invokeMethod ( this,"call",Qt::ConnectionType::QueuedConnection );
}

void CLaterCall::call() {
    target();
}
