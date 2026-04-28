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

#include "core/CConcepts.h"
#include "core/CGlobal.h"

namespace CJsonUtil {
struct JsonParseError {
    std::string source;
    std::string message;
    std::string preview;
    std::source_location location;
};

using JsonParseResult = std::expected<std::shared_ptr<json>, JsonParseError>;

inline std::shared_ptr<json> alias(const std::shared_ptr<json> &owner, json &value) {
    return std::shared_ptr<json>(owner, &value);
}

inline std::string preview_json(std::string text, size_t limit = 120) {
    for (char &ch : text) {
        if (ch == '\n' || ch == '\r' || ch == '\t') {
            ch = ' ';
        }
    }
    if (text.empty()) {
        return "<empty>";
    }
    if (text.size() <= limit) {
        return text;
    }
    return text.substr(0, limit) + "...";
}

inline void log_parse_error(const JsonParseError &error) {
    vstd::logger::warning("Failed to parse json from", error.source.empty() ? "<unknown>" : error.source, ":",
                          error.message, "preview:", error.preview);
}

template <fn::JsonObjectPointer T> bool hasStringProp(T object, std::string prop) {
    return object->count(prop) && (*object)[prop].is_string();
}

template <fn::JsonObjectPointer T> bool hasObjectProp(T object, std::string prop) {
    return object->count(prop) && (*object)[prop].is_object();
}

template <fn::JsonObjectPointer T> bool isRef(T object) {
    if (object->size() == 1) {
        return hasStringProp(object, "ref");
    } else if (object->size() == 2) {
        return hasObjectProp(object, "properties") && hasStringProp(object, "ref");
    }
    return false;
}

template <fn::JsonObjectPointer T> bool isType(T object) {
    if (object->size() == 1) {
        return hasStringProp(object, "class");
    } else if (object->size() == 2) {
        return hasObjectProp(object, "properties") && hasStringProp(object, "class");
    }
    return false;
}

template <fn::JsonObjectPointer T> bool isObject(T object) { return isRef(object) || isType(object); }

template <fn::JsonMapPointer T> bool isMap(T object) {
    for (auto [key, value] : object->items()) {
        (void)key; // to silence compiler
        if (!value.is_object() || !isObject(&value)) {
            return false;
        }
    }
    return true;
}

inline JsonParseResult parse_expected(std::string json_string, const std::string &source = std::string(),
                                      std::source_location location = std::source_location::current()) {
    try {
        return std::make_shared<json>(json::parse(json_string));
    } catch (const std::exception &exception) {
        return std::unexpected(
            JsonParseError{source, exception.what(), preview_json(std::move(json_string)), location});
    }
}

template <typename T = void>
std::shared_ptr<json> from_string(std::string json_string, const std::string &source = std::string()) {
    auto result = parse_expected(std::move(json_string), source);
    if (!result) {
        log_parse_error(result.error());
        return nullptr;
    }
    return *result;
    //        vstd::logger::debug(json,reader.getFormatedErrorMessages());
}

template <fn::JsonDumpPointer T> std::string to_string(T value, int indent = -1) { return value->dump(indent); }

inline std::shared_ptr<json> clone(const json &value) { return std::make_shared<json>(value); }

inline std::shared_ptr<json> clone(const std::shared_ptr<json> &value) { return std::make_shared<json>(*value); }

inline std::shared_ptr<json> clone(const json *value) { return std::make_shared<json>(*value); }
} // namespace CJsonUtil
