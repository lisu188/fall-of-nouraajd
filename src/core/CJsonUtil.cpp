#include "core/CJsonUtil.h"
#include "core/CUtil.h"

bool CJsonUtil::hasStringProp ( std::shared_ptr<Value> object, std::string prop ) {
    Value::ConstMemberIterator it = object->FindMember ( prop.c_str() );
    return it != object->MemberEnd() && it->value.IsString() && vstd::trim(vstd::str(it->value.GetString())) != "";
}

bool CJsonUtil::hasObjectProp ( std::shared_ptr<Value> object, std::string prop ) {
    auto it = object->FindMember ( prop.c_str() );
    return it != object->MemberEnd() && it->value.IsObject();
}

bool CJsonUtil::isRef ( std::shared_ptr<Value> object ) {
    if ( object->Size() == 1 ) {
        return hasStringProp ( object, "ref" );
    } else if ( object->Size() == 2 ) {
        return hasObjectProp ( object, "properties" ) && hasStringProp ( object, "ref" );
    }
    return false;
}

bool CJsonUtil::isType ( std::shared_ptr<Value> object ) {
    if ( object->Size() == 1 ) {
        return hasStringProp ( object, "class" );
    } else if ( object->Size() == 2 ) {
        return hasObjectProp ( object, "properties" ) && hasStringProp ( object, "class" );
    }
    return false;
}

bool CJsonUtil::isObject ( std::shared_ptr<Value> object ) {
    return isRef ( object ) || isType ( object );
}

bool CJsonUtil::isMap ( std::shared_ptr<Value> object ) {
    for ( auto it = object->MemberBegin(); it != object->MemberEnd(); it++ ) {
        if ( !it.->value.IsObject() ||
                !isObject ( std::make_shared<Value> ( it->value ) ) ) {
            return false;
        }
    }
    return true;
}
