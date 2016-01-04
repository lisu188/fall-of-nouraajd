#pragma once

#include "core/CGlobal.h"

namespace CJsonUtil {
    bool hasStringProp ( std::shared_ptr<QJsonObject> object, std::string prop );

    bool hasObjectProp ( std::shared_ptr<QJsonObject> object, std::string prop );

    bool isRef ( std::shared_ptr<QJsonObject> object );

    bool isType ( std::shared_ptr<QJsonObject> object );

    bool isObject ( std::shared_ptr<QJsonObject> object );

    bool isMap ( std::shared_ptr<QJsonObject> object );
}
