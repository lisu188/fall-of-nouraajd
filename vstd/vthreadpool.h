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

#include <thread>

namespace vstd {
    namespace detail {
        class worker_thread {
        public:
            template<typename thread_pool>
            void operator()(std::shared_ptr<thread_pool> pool, std::shared_ptr<worker_thread> self) {
                do {
                    pool->_queue.pop(vstd::functional::call<std::function<void() >>);
                } while (self.use_count() > 1);
            }
        };
    }

    template<int _worker_count, typename worker_thread=detail::worker_thread>
    class thread_pool : public std::enable_shared_from_this<thread_pool<_worker_count, worker_thread>> {
        friend worker_thread;
    public:
        template<typename F, typename... Args>
        void execute(F f, Args... args) {
            _queue.push(vstd::bind(f, args...));
        }

        std::shared_ptr<thread_pool> start() {
            std::unique_lock<std::recursive_mutex> lock(_worker_lock);
            while (_workers.size() < _worker_count) {
                add_worker();
            }
            return this->shared_from_this();
        }

    private:
        void add_worker() {
            std::unique_lock<std::recursive_mutex> lock(_worker_lock);
            auto worker = std::make_shared<worker_thread>();
            _workers.insert(worker);
            std::thread(*worker, this->shared_from_this(), worker).detach();
        }

        void del_worker() {
            std::unique_lock<std::recursive_mutex> lock(_worker_lock);
            _workers.erase(_workers.begin());
        }

        vstd::blocking_queue<std::function<void() >> _queue;
        std::set<std::shared_ptr<worker_thread>> _workers;
        std::recursive_mutex _worker_lock;
    };
}
