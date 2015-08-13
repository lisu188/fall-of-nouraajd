#pragma once

namespace vstd {
    template<typename T>
    QString to_hex ( T object ) {
        std::stringstream stream;
        stream << std::hex << object;
        return QString::fromStdString ( stream.str() ).toUpper();
    }

    template<typename T>
    QString to_hex ( T* object ) {
        return to_hex ( long ( object ) );
    }

    template<typename T>
    QString to_hex ( std::shared_ptr<T> object ) {
        return to_hex ( object.get() );
    }

    template<typename T>
    QString to_hex_hash ( T object ) {
        return to_hex ( hash_combine ( object ) );
    }
}
