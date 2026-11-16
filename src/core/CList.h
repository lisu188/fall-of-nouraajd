/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025-2026  Andrzej Lis

This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
#pragma once

#include "object/CGameObject.h"

namespace collection_detail {
template <typename Values>
    requires(fn::SetLike<Values> || fn::MapLike<Values>)
class CValues : public CGameObject {
  public:
    void setValues(Values _values) { values = _values; }

    Values getValues() { return values; }

  protected:
    Values values;
};

template <typename Value> class CSetValues : public CValues<std::set<Value>> {
  public:
    void addValue(Value val) { this->values.insert(val); }
};
}

class CListString : public collection_detail::CSetValues<std::string> {
    V_META(CListString, CGameObject, V_PROPERTY(CListString, std::set<std::string>, values, getValues, setValues))
  public:
    CListString() = default;
};

class CListInt : public collection_detail::CSetValues<int> {
    V_META(CListInt, CGameObject, V_PROPERTY(CListInt, std::set<int>, values, getValues, setValues))
  public:
    CListInt() = default;
};

typedef std::map<std::string, std::string> string_string_map;
typedef std::map<std::string, int> string_int_map;
typedef std::map<int, std::string> int_string_map;
typedef std::map<int, int> int_int_map;

class CMapStringString : public collection_detail::CValues<string_string_map> {
    V_META(CMapStringString, CGameObject, V_PROPERTY(CMapStringString, string_string_map, values, getValues, setValues))
  public:
    CMapStringString() = default;
};

class CMapStringInt : public collection_detail::CValues<string_int_map> {
    V_META(CMapStringInt, CGameObject, V_PROPERTY(CMapStringInt, string_int_map, values, getValues, setValues))
  public:
    CMapStringInt() = default;
};

class CMapIntString : public collection_detail::CValues<int_string_map> {
    V_META(CMapIntString, CGameObject, V_PROPERTY(CMapIntString, int_string_map, values, getValues, setValues))
  public:
    CMapIntString() = default;
};

class CMapIntInt : public collection_detail::CValues<int_int_map> {
    V_META(CMapIntInt, CGameObject, V_PROPERTY(CMapIntInt, int_int_map, values, getValues, setValues))
  public:
    CMapIntInt() = default;
};
