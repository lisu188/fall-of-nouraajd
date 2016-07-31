#pragma once

#include "core/CGlobal.h"
#include "object/CGameObject.h"

class CEventLoop : public CGameObject {

public:
    static std::shared_ptr<CEventLoop> instance();

    void invoke(std::function<void()> f);

    void await(std::function<void()> f);

    void run();

    Uint32 _call_function_event = SDL_RegisterEvents(1);;
    std::thread::id _main_thread_id = std::this_thread::get_id();

    CEventLoop();

    ~CEventLoop();
};

