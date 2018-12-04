#include "CGlobal.h"


namespace vstd {
    std::function<void(std::function<void()>)> get_call_later_handler() {
        return [](std::function<void()> f) {
            vstd::event_loop<>::instance()->invoke(f);
        };
    }

    std::function<void(std::function<void()>)> get_call_async_handler() {
        return [](std::function<void()> f) {
            static std::shared_ptr<vstd::thread_pool<16>> pool = std::make_shared<vstd::thread_pool<16>>()->start();
            pool->execute(f);
        };
    }

    std::function<void(std::function<void()>)> get_call_later_block_handler() {
        return [](std::function<void()> f) {
            vstd::event_loop<>::instance()->await(f);
        };
    }

    std::function<void(std::function<bool()>)> get_wait_until_handler() {
        return [](std::function<bool()> pred) {
            vstd::call_later_block([pred]() {
                while (!pred()) {
                    vstd::event_loop<>::instance()->run();
                }
            });
        };
    }

    std::function<void(int, std::function<void()>)> get_call_delayed_later_handler() {
        return [](int t, std::function<void()> f) {
            vstd::event_loop<>::instance()->delay(t, f);
        };
    }

    std::function<void(int, std::function<void()>)> get_call_delayed_async_handler() {
        return [](int t, std::function<void()> f) {
            vstd::event_loop<>::instance()->delay(t, [f]() {
                vstd::async(f);
            });
        };
    }
}


