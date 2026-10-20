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
#include "LegacyJsonParser.h"

#include <simdjson.h>

namespace {
json fromSimdjson(const simdjson::dom::element &element);

std::runtime_error simdjsonError(const std::string &context, simdjson::error_code error) {
    return std::runtime_error(context + ": " + simdjson::error_message(error));
}

json fromSimdjsonArray(const simdjson::dom::element &element) {
    simdjson::dom::array array;
    if (auto error = element.get_array().get(array); error != simdjson::SUCCESS) {
        throw simdjsonError("failed to read JSON array", error);
    }

    json result = json::array();
    for (auto child : array) {
        result[result.size()] = fromSimdjson(child);
    }
    return result;
}

json fromSimdjsonObject(const simdjson::dom::element &element) {
    simdjson::dom::object object;
    if (auto error = element.get_object().get(object); error != simdjson::SUCCESS) {
        throw simdjsonError("failed to read JSON object", error);
    }

    json result = json::object();
    for (simdjson::dom::key_value_pair field : object) {
        const auto key = std::string(field.key);
        if (result.contains(key)) {
            throw std::runtime_error("duplicate JSON object key: " + key);
        }
        result[key] = fromSimdjson(field.value);
    }
    return result;
}

json fromSimdjson(const simdjson::dom::element &element) {
    switch (element.type()) {
    case simdjson::dom::element_type::ARRAY:
        return fromSimdjsonArray(element);
    case simdjson::dom::element_type::OBJECT:
        return fromSimdjsonObject(element);
    case simdjson::dom::element_type::STRING: {
        std::string_view value;
        if (auto error = element.get_string().get(value); error != simdjson::SUCCESS) {
            throw simdjsonError("failed to read JSON string", error);
        }
        return json(std::string(value));
    }
    case simdjson::dom::element_type::INT64: {
        std::int64_t value = 0;
        if (auto error = element.get_int64().get(value); error != simdjson::SUCCESS) {
            throw simdjsonError("failed to read JSON integer", error);
        }
        return json(static_cast<long long>(value));
    }
    case simdjson::dom::element_type::UINT64: {
        std::uint64_t value = 0;
        if (auto error = element.get_uint64().get(value); error != simdjson::SUCCESS) {
            throw simdjsonError("failed to read JSON unsigned integer", error);
        }
        return json(static_cast<unsigned long long>(value));
    }
    case simdjson::dom::element_type::DOUBLE: {
        double value = 0;
        if (auto error = element.get_double().get(value); error != simdjson::SUCCESS) {
            throw simdjsonError("failed to read JSON number", error);
        }
        return json(value);
    }
    case simdjson::dom::element_type::BOOL: {
        bool value = false;
        if (auto error = element.get_bool().get(value); error != simdjson::SUCCESS) {
            throw simdjsonError("failed to read JSON boolean", error);
        }
        return json(value);
    }
    case simdjson::dom::element_type::NULL_VALUE:
        return json(nullptr);
    case simdjson::dom::element_type::BIGINT: {
        std::string_view value;
        if (auto error = element.get_string().get(value); error != simdjson::SUCCESS) {
            throw simdjsonError("failed to read JSON bigint", error);
        }
        return json(std::string(value));
    }
    }
    return json(nullptr);
}

} // namespace

json legacyJsonParse(std::string_view text) {
    simdjson::dom::parser parser;
    simdjson::padded_string padded(text);
    simdjson::dom::element element;
    if (auto error = parser.parse(padded).get(element); error != simdjson::SUCCESS) {
        throw simdjsonError("failed to parse JSON", error);
    }
    return fromSimdjson(element);
}
