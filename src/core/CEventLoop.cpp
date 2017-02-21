#include "core/CEventLoop.h"

std::shared_ptr<CEventLoop> CEventLoop::instance() {
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

bool CEventLoop::run() {
    int frameTime = SDL_GetTicks();

    SDL_Event event;
    while (SDL_PollEvent(&event)) {
        if (event.type == SDL_QUIT) {
            return false;
        }
        for (auto cm:eventCallbackList) {
            cm(&event);
        }
    }

    while (!delayQueue.empty() && delayQueue.top().first < frameTime) {
        delayQueue.top().second();
        delayQueue.pop();
    }

    for (auto f:frameCallbackList) {
        f(frameTime);
    }

    int endTime = SDL_GetTicks();
    int actualFrameTime = endTime - lastFrameTime;
    int desiredFrameTime = 1000 / FPS;

    int diffTime = desiredFrameTime - actualFrameTime;
    if (diffTime < 0) {
        vstd::logger::warning("CEventLoop:", "cannot achieve specified fps!");
    } else {
        SDL_Delay(diffTime);
    }

    this->lastFrameTime = SDL_GetTicks();

    return true;
}

CEventLoop::CEventLoop() {
    SDL_Init(SDL_INIT_EVENTS);
    registerEventCallback([=](SDL_Event *event) {
        if (event->type == _call_function_event) {
            static_cast<std::function<void()> *>(event->user.data1)->operator()();
            delete static_cast<std::function<void()> *>(event->user.data1);
        }
    });
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

void CEventLoop::delay(int t, std::function<void()> f) {
    if (std::this_thread::get_id() == _main_thread_id) {
        delayQueue.push(std::make_pair(SDL_GetTicks() + t, f));
    } else {
        vstd::later([this, t, f]() {
            delayQueue.push(std::make_pair(SDL_GetTicks() + t, f));
        });
    }
}

void CEventLoop::registerFrameCallback(std::function<void(int)> f) {
    frameCallbackList.push_back(f);
}

void CEventLoop::registerEventCallback(std::function<void(SDL_Event *)> f) {
    eventCallbackList.push_back(f);
}


