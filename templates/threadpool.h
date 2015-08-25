#pragma once
#include "CGlobal.h"
#include "templates/yield.h"

namespace vstd {
    namespace detail {
        class worker_thread {
        public:
            template<typename thread_pool>
            void operator() ( std::shared_ptr<thread_pool> pool,std::shared_ptr<worker_thread> self ) {
                vstd::register_yield ( [pool,self]() {
                    pool->_queue.pop ( vstd::call<std::function<void() >> );
                } );
                do {
                    pool->_queue.pop ( vstd::call<std::function<void() >> );
                } while ( self.use_count() > 1 );
            }
        };
    }

    template<int _worker_count,typename worker_thread=detail::worker_thread>
    class thread_pool : public std::enable_shared_from_this<thread_pool<_worker_count,worker_thread>> {
        friend worker_thread;
    public:
        template<typename F,typename... Args>
        void execute ( F f,Args... args ) {
            _queue.push ( vstd::bind ( f,args... ) );
            {
                std::unique_lock<std::recursive_mutex> lock ( _worker_lock );
                if ( _workers.size() < _worker_count ) {
                    add_worker();
                } else if ( _workers.size() > _worker_count ) {
                    del_worker();
                }
            }
        }
    private:
        void add_worker() {
            std::unique_lock<std::recursive_mutex> lock ( _worker_lock );
            auto worker=std::make_shared<worker_thread> ( );
            _workers.insert ( worker );
            std::thread ( *worker,this->shared_from_this(),worker ).detach();
        }
        void del_worker() {
            std::unique_lock<std::recursive_mutex> lock ( _worker_lock );
            _workers.erase ( _workers.begin() );
        }
        vstd::blocking_queue<std::function<void() >> _queue;
        std::set<std::shared_ptr<worker_thread>> _workers;
        std::recursive_mutex _worker_lock;
    };
}
