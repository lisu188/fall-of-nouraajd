#include "core/CGlobal.h"
#include "core/CTypes.h"

//TODO:
//namespace vstd {
//    std::function<void(std::function<void()>)> get_call_later_handler() {
//        return [](std::function<void()> f) {
//            QApplication::postEvent(CInvocationHandler::instance(),
//                                    new CInvocationEvent(f));
//        };
//    }
//
//    std::function<void(std::function<void()>)> get_call_async_handler() {
//        return [](std::function<void()> f) {
//            static std::shared_ptr<vstd::thread_pool<16>> pool = std::make_shared<vstd::thread_pool<16>>()->start();
//            pool->execute(f);
//        };
//    }
//
//    std::function<void(std::function<void()>)> get_call_later_block_handler() {
//        return [](std::function<void()> f) {
//            QApplication::sendEvent(CInvocationHandler::instance(),
//                                    new CInvocationEvent(f));
//        };
//    }
//
//    std::function<void(std::function<bool()>)> get_wait_until_handler() {
//        return [](std::function<bool()> pred) {
//            vstd::call_later_block([pred]() {
//                while (!pred()) {
//                    QApplication::processEvents(QEventLoop::WaitForMoreEvents);
//                }
//            });
//        };
//    }
//}

int main(int argc, char *argv[]) {
    CTypes::initialize();
    if (argc == 2) {
        CResourcesProvider::getInstance()->save(std::string(argv[1]),
                                                CResourcesProvider::getInstance()->load(std::string(argv[1])));
    }
    //TODO:
//    else {
//        QApplication a ( argc, argv );
//        CMainWindow window;
//        window.show();
//        return a.exec();
//    }
    return 0;
}

