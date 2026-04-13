/*
 * MIT License
 *
 * Copyright (c) 2025 Andrzej Lis
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */
#pragma once

#include <cstdio>
#include <cstring>
#include <list>
#include <string>
#include <sstream>
#include <algorithm>
#include <functional>
#include <cctype>
#include <locale>
#include <type_traits>
#include <boost/filesystem.hpp>
#include <boost/algorithm/string.hpp>
#include <utility>
#include "vdefines.h"
#include "vutil.h"

namespace vstd {
    template<typename T, typename = void>
    struct has_to_std_string : std::false_type {};

    template<typename T>
    struct has_to_std_string<T, std::void_t<decltype(std::declval<T>().toStdString())>> : std::true_type {};

    class stringable {
    public:
        virtual std::string to_string() = 0;
    };

    template<typename T=void>
    std::string replace(std::string str, const std::string &from, const std::string &to) {
        size_t start_pos = str.find(from);
        if (start_pos == std::string::npos) {
            return str;
        }
        str.replace(start_pos, from.length(), to);
        return replace(str, from, to);
    }

    template<typename T=void>
    std::string ltrim(std::string s) {
        s.erase(s.begin(), std::find_if(s.begin(), s.end(), std::not_fn<int(int)>(std::isspace)));
        return s;
    }

    template<typename T=void>
    std::string rtrim(std::string s) {
        s.erase(std::find_if(s.rbegin(), s.rend(), std::not_fn<int(int)>(std::isspace)).base(), s.end());
        return s;
    }

    template<typename T=void>
    std::string trim(const std::string &s) {
        return ltrim(rtrim(s));
    }

    template<typename T=void>
    bool is_empty(const std::string &string) {
        return trim(string).length() == 0;
    }

    template<typename T, typename std::enable_if<!has_to_std_string<T>::value, int>::type = 0>
    std::string str(T c) {
        std::stringstream st;
        st << c;
        return st.str();
    }

    template<typename T, typename std::enable_if<has_to_std_string<T>::value, int>::type = 0>
    std::string str(const T &c) {
        return c.toStdString();
    }

    template<typename T, typename... Args>
    std::string str(T c, Args... args) {
        std::stringstream st;
        st << c;
        return st.str() + vstd::str(args...);
    }

    template<typename T=void>
    std::string str(const std::shared_ptr<stringable> &c) {
        return c->to_string();
    }

    template<typename T=void>
    std::pair<int, bool> to_int(const std::string &s) {
        if (isdigit(s[0])) {
            try {
                size_t result;
                int value = std::stoi(s, &result);
                if (result != s.size()) {
                    return std::make_pair(value, false);
                }
                return std::make_pair(value, true);
            } catch (...) {
            }
        }
        return std::make_pair(0, false);
    }

    template<typename T=void>
    bool is_int(const std::string &s) {
        return to_int(s).second;
    }

    template<typename Ctn=std::list<std::string> >
    std::string join(Ctn list, const std::string &sep) {
        std::stringstream stream;
        unsigned int i = 0;
        for (const std::string &str: list) {
            stream << str;
            if (i++ != list.size() - 1) {
                stream << sep;
            }
        }
        return stream.str();
    }

    template<typename T=void>
    std::vector<std::string> split(const std::string &s, char delim) {
        std::vector<std::string> elems;
        std::stringstream ss(s);
        std::string item;
        while (std::getline(ss, item, delim)) {
            elems.push_back(item);
        }
        return elems;
    }

    template<typename T, typename U>
    bool string_equals(T a, U b) {
        return str(a) == str(b);
    }

    template<typename T=void>
    bool ends_with(const std::string &full_string, const std::string &ending) {
        if (full_string.length() >= ending.length()) {
            return (0 == full_string.compare(full_string.length() - ending.length(), ending.length(), ending));
        } else {
            return false;
        }
    }

    template<typename T=void>
    wchar_t *to_wchar(const char *text) {
        size_t size = strlen(text) + 1;
        auto *wa = new wchar_t[size];
        mbstowcs(wa, text, size);
        return wa;
    }

    template<typename T=void>
    wchar_t **to_wchar(int size, const char **text) {
        auto **wa = new wchar_t *[size];
        for (int i = 0; i < size; i++) {
            wa[i] = to_wchar(text[i]);
        }
        return wa;
    }

    template<typename T=void>
    std::string stem(const std::string &script) {
        return boost::filesystem::path(script).stem().string();
    }

    template<typename T=void>
    void add_line(std::string &org, const std::string &_new) {
        if (!_new.empty()) {
            org += "\n" + _new;
        }
    }

    template<typename T=void>
    std::string camel(std::string org) {
        if (ctn(org, ' ')) {
            std::string ret;
            for (const auto &str: split(org, ' ')) {
                ret += (camel(str) + " ");
            }
            return ret;
        }
        return boost::to_upper_copy<std::string>(org.substr(0, 1)) + org.substr(1, org.length());
    }
}
