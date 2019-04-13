#pragma once

#include "object/CGameObject.h"

class CList : public CGameObject {
V_META(CList, CGameObject,
       V_PROPERTY(CList, std::set<std::string>, values, getValues, setValues))
public:
    CList() = default;

private:
    std::set<std::string> values;
public:
    void setValues(std::set<std::string> _values) {
        this->values = _values;
    }

    std::set<std::string> getValues() {
        return values;
    }
};