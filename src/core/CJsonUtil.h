#pragma once

#include "core/CGlobal.h"

namespace CJsonUtil {
    bool hasStringProp ( std::shared_ptr<Value> object, std::string prop );

    bool hasObjectProp ( std::shared_ptr<Value> object, std::string prop );

    bool isRef ( std::shared_ptr<Value> object );

    bool isType ( std::shared_ptr<Value> object );

    bool isObject ( std::shared_ptr<Value> object );

    bool isMap ( std::shared_ptr<Value> object );
}
