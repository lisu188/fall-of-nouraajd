/*
 * MIT License
 *
 * Copyright (c) 2019 Andrzej Lis
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */
#pragma once

#include "vfuture.h"

namespace vstd {
    template<typename T=void>
    class event_loop {
        struct DelayCompare {
            bool operator()(const std::pair<int, std::function<void()>> &a, std::pair<int, std::function<void()>> b) {
                return std::greater<int>()(a.first, b.first);
            }
        };

        int lastFrameTime = SDL_GetTicks();
        Uint32 _call_function_event = SDL_RegisterEvents(1);
        std::thread::id _main_thread_id = std::this_thread::get_id();

        std::priority_queue<std::pair<int, std::function<void()>>,
                std::vector<std::pair<int, std::function<void()>>>,
                DelayCompare> delayQueue;
        std::list<std::pair<std::function<bool()>, std::function<void()>>> conditionalQueue;

        std::list<std::function<void(int)>> frameCallbackList;
        std::list<std::function<bool(SDL_Event *)>> eventCallbackList;
    public:
        static std::shared_ptr<event_loop> instance() {
            static std::shared_ptr<vstd::event_loop<>> _loop = std::make_shared<vstd::event_loop<>>();
            return _loop;
        }

        void invoke(const std::function<void()> &f) {
            SDL_Event event;
            SDL_zero(event);
            event.type = _call_function_event;
            event.user.data1 = new std::function<void()>(f);
            SDL_PushEvent(&event);
        }

        void invoke_when(const std::function<bool()> &pred, const std::function<void()> &func) {
            invoke([=, this]() {
                conditionalQueue.emplace_back(pred, func);
            });
        }

        void await(const std::function<void()> &f) {
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

        void delay(int t, const std::function<void()> &f) {
            if (std::this_thread::get_id() == _main_thread_id) {
                delayQueue.push(std::make_pair(SDL_GetTicks() + t, f));
            } else {
                vstd::later([=, this]() {
                    delayQueue.push(std::make_pair(SDL_GetTicks() + t, f));
                });
            }
        }

        void registerFrameCallback(const std::function<void(int)> &f) {
            frameCallbackList.push_back(f);
        }

        void registerEventCallback(const std::function<bool(SDL_Event *)> &f) {
            eventCallbackList.push_back(f);
        }

        bool run() {
            int frameTime = SDL_GetTicks();

            SDL_Event event;
            while (SDL_PollEvent(&event)) {
                if (event.type == SDL_QUIT) {
                    return false;
                }
                for (const auto &cm:eventCallbackList) {
                    if (cm(&event)) {
                        break;
                    }
                }
            }

            auto it = conditionalQueue.begin();
            while (it != conditionalQueue.end()) {
                if (it->first()) {
                    it->second();
                    it = conditionalQueue.erase(it);
                } else {
                    ++it;
                }
            }

            while (!delayQueue.empty() && delayQueue.top().first < frameTime) {
                delayQueue.top().second();
                delayQueue.pop();
            }

            for (const auto &f:frameCallbackList) {
                f(frameTime);
            }

            int endTime = SDL_GetTicks();
            int actualFrameTime = endTime - lastFrameTime;
            int desiredFrameTime = 1000 / fps;

            int diffTime = desiredFrameTime - actualFrameTime;
            if (diffTime < 0) {
                //TODO: vstd::logger::warning("CEventLoop:", "cannot achieve specified fps!");
            } else {
                SDL_Delay(diffTime);
            }

            this->lastFrameTime = SDL_GetTicks();

            return true;
        }

        event_loop() {
            SDL_Init(SDL_INIT_EVENTS);
            registerEventCallback([this](SDL_Event *event) {
                if (event->type == _call_function_event) {
                    static_cast<std::function<void()> *>(event->user.data1)->operator()();
                    delete static_cast<std::function<void()> *>(event->user.data1);
                    return true;
                }
                return false;
            });
        }

        ~event_loop() {
            SDL_Quit();
        }

    private:
        int fps = 100;
    public:
        int getFps() {
            return fps;
        }

        void setFps(int fps) {
            this->fps = fps;
        }
    };
}
