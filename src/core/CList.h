#pragma once

#include "object/CGameObject.h"

class CListString : public CGameObject {
V_META(CListString, CGameObject,
       V_PROPERTY(CListString, std::set<std::string>, values, getValues, setValues))
public:
    CListString() = default;

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

class CListInt : public CGameObject {
V_META(CListInt, CGameObject,
       V_PROPERTY(CListInt, std::set<int>, values, getValues, setValues))
public:
    CListInt() = default;

private:
    std::set<int> values;
public:
    void setValues(std::set<int> _values) {
        this->values = _values;
    }

    std::set<int> getValues() {
        return values;
    }
};

typedef std::map<std::string, std::string> string_string_map;
typedef std::map<std::string, int> string_int_map;
typedef std::map<int, std::string> int_string_map;
typedef std::map<int, int> int_int_map;

class CMapStringString : public CGameObject {
V_META(CMapStringString, CGameObject,
       V_PROPERTY(CMapStringString, string_string_map, values, getValues, setValues))
public:
    CMapStringString() = default;

private:
    std::map<std::string, std::string> values;
public:
    void setValues(std::map<std::string, std::string> _values) {
        this->values = _values;
    }

    std::map<std::string, std::string> getValues() {
        return values;
    }
};

class CMapStringInt : public CGameObject {
V_META(CMapStringInt, CGameObject,
       V_PROPERTY(CMapStringInt, string_int_map, values, getValues, setValues))
public:
    CMapStringInt() = default;

private:
    std::map<std::string, int> values;
public:
    void setValues(std::map<std::string, int> _values) {
        this->values = _values;
    }

    std::map<std::string, int> getValues() {
        return values;
    }
};

class CMapIntString : public CGameObject {
V_META(CMapIntString, CGameObject,
       V_PROPERTY(CMapIntString, int_string_map, values, getValues, setValues))
public:
    CMapIntString() = default;

private:
    std::map<int, std::string> values;
public:
    void setValues(std::map<int, std::string> _values) {
        this->values = _values;
    }

    std::map<int, std::string> getValues() {
        return values;
    }
};


class CMapIntInt : public CGameObject {
V_META(CMapIntInt, CGameObject,
       V_PROPERTY(CMapIntInt, int_int_map, values, getValues, setValues))
public:
    CMapIntInt() = default;

private:
    std::map<int, int> values;
public:
    void setValues(std::map<int, int> _values) {
        this->values = _values;
    }

    std::map<int, int> getValues() {
        return values;
    }
};