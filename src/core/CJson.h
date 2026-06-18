/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026  Andrzej Lis

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

#include <cstdint>
#include <initializer_list>
#include <map>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <variant>
#include <vector>

class json {
  public:
    using object_t = std::map<std::string, json>;
    using array_t = std::vector<json>;

    json();
    json(std::nullptr_t);
    json(const char *value);
    json(std::string value);
    json(bool value);
    json(int value);
    json(unsigned int value);
    json(long value);
    json(unsigned long value);
    json(long long value);
    json(unsigned long long value);
    json(double value);
    json(std::initializer_list<object_t::value_type> values);

    static json object();
    static json array();
    static json array(std::initializer_list<json> values);
    static json parse(const char *text);
    static json parse(const std::string &text);
    static json parse(std::string_view text);

    bool is_null() const;
    bool is_object() const;
    bool is_array() const;
    bool is_string() const;
    bool is_boolean() const;
    bool is_number() const;
    bool is_number_integer() const;
    bool empty() const;
    std::size_t size() const;
    std::size_t count(const std::string &key) const;
    bool contains(const std::string &key) const;

    json &operator[](const std::string &key);
    json &operator[](const char *key);
    const json &operator[](const std::string &key) const;
    const json &operator[](const char *key) const;
    json &operator[](int index);
    const json &operator[](int index) const;
    json &operator[](unsigned int index);
    const json &operator[](unsigned int index) const;
    json &operator[](std::size_t index);
    const json &operator[](std::size_t index) const;
    json &at(const std::string &key);
    const json &at(const std::string &key) const;
    json &at(std::size_t index);
    const json &at(std::size_t index) const;
    void erase(const std::string &key);

    object_t &items();
    const object_t &items() const;
    array_t::iterator begin();
    array_t::iterator end();
    array_t::const_iterator begin() const;
    array_t::const_iterator end() const;
    array_t::const_iterator cbegin() const;
    array_t::const_iterator cend() const;

    template <typename T> T value(const std::string &key, T fallback) const {
        if (!contains(key)) {
            return fallback;
        }
        try {
            return (*this)[key].template get<T>();
        } catch (const std::exception &) {
            return fallback;
        }
    }

    template <typename T> T get() const {
        if constexpr (std::is_same_v<T, std::string>) {
            if (!is_string()) {
                throw std::runtime_error("json value is not a string");
            }
            return std::get<std::string>(data);
        } else if constexpr (std::is_same_v<T, bool>) {
            if (!is_boolean()) {
                throw std::runtime_error("json value is not a boolean");
            }
            return std::get<bool>(data);
        } else if constexpr (std::is_same_v<T, int>) {
            auto value = get<long long>();
            return static_cast<int>(value);
        } else if constexpr (std::is_same_v<T, long>) {
            auto value = get<long long>();
            return static_cast<long>(value);
        } else if constexpr (std::is_same_v<T, long long>) {
            if (std::holds_alternative<std::int64_t>(data)) {
                return static_cast<long long>(std::get<std::int64_t>(data));
            }
            if (std::holds_alternative<std::uint64_t>(data)) {
                return static_cast<long long>(std::get<std::uint64_t>(data));
            }
            throw std::runtime_error("json value is not an integer");
        } else if constexpr (std::is_same_v<T, unsigned int>) {
            auto value = get<unsigned long long>();
            return static_cast<unsigned int>(value);
        } else if constexpr (std::is_same_v<T, unsigned long>) {
            auto value = get<unsigned long long>();
            return static_cast<unsigned long>(value);
        } else if constexpr (std::is_same_v<T, unsigned long long>) {
            if (std::holds_alternative<std::uint64_t>(data)) {
                return static_cast<unsigned long long>(std::get<std::uint64_t>(data));
            }
            if (std::holds_alternative<std::int64_t>(data)) {
                return static_cast<unsigned long long>(std::get<std::int64_t>(data));
            }
            throw std::runtime_error("json value is not an unsigned integer");
        } else if constexpr (std::is_same_v<T, double>) {
            if (std::holds_alternative<double>(data)) {
                return std::get<double>(data);
            }
            if (std::holds_alternative<std::int64_t>(data)) {
                return static_cast<double>(std::get<std::int64_t>(data));
            }
            if (std::holds_alternative<std::uint64_t>(data)) {
                return static_cast<double>(std::get<std::uint64_t>(data));
            }
            throw std::runtime_error("json value is not numeric");
        } else {
            static_assert(!sizeof(T), "unsupported json::get<T>() type");
        }
    }

    std::string dump(int indent = -1) const;

  private:
    using storage_t =
        std::variant<std::nullptr_t, object_t, array_t, std::string, std::int64_t, std::uint64_t, double, bool>;

    storage_t data;

    object_t &ensureObject();
    array_t &ensureArray();
    const object_t *objectPtr() const;
    const array_t *arrayPtr() const;
    static const json &nullValue();
    static const object_t &emptyObject();
    static const array_t &emptyArray();
};
