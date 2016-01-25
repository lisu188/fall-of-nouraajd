#include "core/CEventLoop.h"

std::shared_ptr<CEventLoop>  CEventLoop::instance() {
    static std::shared_ptr<CEventLoop> _loop = std::make_shared<CEventLoop>();
    return _loop;
}

void CEventLoop::invoke(std::function<void()> f) {
    SDL_Event event;
    SDL_zero(event);
    event.type = _call_function_event;
    event.user.data1 = new std::function<void()>(f);
    SDL_PushEvent(&event);
}

void CEventLoop::run() {
    SDL_Event event;
    if (SDL_WaitEvent(&event)) {
        if (event.type == _call_function_event) {
            static_cast<std::function<void()> *>(event.user.data1)->operator()();
            delete static_cast<std::function<void()> *>(event.user.data1);
        }
    }
}

CEventLoop::CEventLoop() {
    SDL_Init(SDL_INIT_EVENTS);
}

CEventLoop::~CEventLoop() {
    SDL_Quit();
}

void CEventLoop::await(std::function<void()> f) {
    if (std::this_thread::get_id() == _main_thread_id) {
        f();
    } else {
        std::recursive_mutex _mutex;
        std::unique_lock<std::recursive_mutex> _lock(_mutex);
        bool completed = false;
        std::condition_variable_any _condition;
        invoke([&]() {
            std::unique_lock<std::recursive_mutex> __lock(_mutex);
            f();
            completed = true;
            _condition.notify_all();
        });
        _condition.wait(_lock, [&]() { return completed; });
    }
}