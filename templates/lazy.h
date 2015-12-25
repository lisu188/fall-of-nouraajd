#pragma once

namespace vstd {
    template<typename T, typename... U>
    class lazy {
    public:
        std::shared_ptr<T> get ( U... parent ) {
            if ( ptr ) {
                return ptr;
            }
            return ptr = std::make_shared<T> ( parent... );
        }

    private :
        std::shared_ptr<T> ptr;
    };
}
