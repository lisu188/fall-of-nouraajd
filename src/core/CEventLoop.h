#pragma once

#include "core/CGlobal.h"
#include "object/CGameObject.h"

//TODO: implement cleaning on the end

class CEventLoop : public CGameObject {
V_META(CEventLoop, CGameObject, V_PROPERTY(CEventLoop, int, fps, getFps, setFps))

    struct DelayCompare {
        bool operator()(std::pair<int, std::function<void()>> a, std::pair<int, std::function<void()>> b) {
            return std::greater<int>()(a.first, b.first);
        }
    };

    int lastFrameTime = SDL_GetTicks();
    Uint32 _call_function_event = SDL_RegisterEvents(1);
    std::thread::id _main_thread_id = std::this_thread::get_id();
    std::priority_queue<std::pair<int, std::function<void()>>,
            std::vector<std::pair<int, std::function<void()>>>,
            DelayCompare> delayQueue;
    std::list<std::function<void(int)>> frameCallbackList;
    std::list<std::function<void(SDL_Event *)>> eventCallbackList;
public:
    static std::shared_ptr<CEventLoop> instance();

    void invoke(std::function<void()> f);

    void await(std::function<void()> f);

    void delay(int t, std::function<void()> f);

    void registerFrameCallback(std::function<void(int)> f);

    void registerEventCallback(std::function<void(SDL_Event *)> f);

    bool run();

    CEventLoop();

    ~CEventLoop();

private:
    int fps = 100;
public:
    int getFps();

    void setFps(int fps);
};

