#pragma once

#include "core/CGlobal.h"

class CEventLoop {
    friend class __gnu_cxx::new_allocator<CEventLoop>;

public:
    static std::shared_ptr<CEventLoop> instance();

    void invoke(std::function<void()> f);

    void await(std::function<void()> f);

    void run();

private:
    Uint32 _call_function_event = SDL_RegisterEvents(1);;
    std::thread::id _main_thread_id = std::this_thread::get_id();

    CEventLoop();

    ~CEventLoop();
};

