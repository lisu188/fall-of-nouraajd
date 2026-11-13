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
#include "core/CJson.h"
#include "core/CJsonParseDiagnostics.h"

#include <cmath>
#include <cstring>
#include <iomanip>
#include <limits>
#include <optional>
#include <sstream>

#include <simdjson.h>

namespace {
constexpr std::size_t retainedInputLimit = 4 * 1024 * 1024;

#ifdef GAME_JSON_DIAGNOSTICS
thread_local game::json_detail::ParseDiagnostics diagnostics;
#define GAME_JSON_RECORD(counter) (++diagnostics.counter)
#else
#define GAME_JSON_RECORD(counter) ((void)0)
#endif

std::runtime_error simdjsonError(const std::string &context, simdjson::error_code error) {
    return std::runtime_error(context + ": " + simdjson::error_message(error));
}

void checkParseError(simdjson::error_code error) {
    if (error != simdjson::SUCCESS) {
        throw simdjsonError("failed to parse JSON", error);
    }
}

struct ParseContext {
    simdjson::dom::parser parser;
    std::vector<char> input;
    bool active = false;

    ParseContext() { GAME_JSON_RECORD(parserCreations); }

    void prepare(std::string_view text) {
        std::size_t capacity = text.size();
        if (capacity <= retainedInputLimit) {
            capacity = 64;
            while (capacity < text.size()) {
                capacity *= 2;
            }
        }
        if (capacity > input.max_size() - simdjson::SIMDJSON_PADDING) {
            throw simdjsonError("failed to parse JSON", simdjson::CAPACITY);
        }
        if (input.size() < capacity + simdjson::SIMDJSON_PADDING) {
            input.resize(capacity + simdjson::SIMDJSON_PADDING);
            GAME_JSON_RECORD(scratchGrowths);
        }
        if (parser.capacity() < capacity) {
            checkParseError(parser.allocate(capacity));
            GAME_JSON_RECORD(parserGrowths);
        }
        if (!text.empty()) {
            std::memcpy(input.data(), text.data(), text.size());
        }
        std::memset(input.data() + text.size(), 0, simdjson::SIMDJSON_PADDING);
    }
};

thread_local ParseContext retainedContext;

class ParseLease {
  public:
    explicit ParseLease(std::size_t size) {
        if (size <= retainedInputLimit && !retainedContext.active) {
            context = &retainedContext;
            context->active = true;
        } else {
            temporary.emplace();
            context = &*temporary;
            GAME_JSON_RECORD(temporaryContexts);
        }
    }

    ParseLease(const ParseLease &) = delete;
    ParseLease &operator=(const ParseLease &) = delete;
    ParseLease(ParseLease &&) = delete;
    ParseLease &operator=(ParseLease &&) = delete;

    ~ParseLease() {
        if (context == &retainedContext) {
            context->active = false;
        }
    }

    ParseContext &get() { return *context; }

  private:
    std::optional<ParseContext> temporary;
    ParseContext *context = nullptr;
};
} // namespace

namespace game::json_detail {
ParseDiagnostics parseDiagnostics() noexcept {
#ifdef GAME_JSON_DIAGNOSTICS
    auto result = diagnostics;
    result.retainedCapacity =
        retainedContext.input.empty() ? 0 : retainedContext.input.size() - simdjson::SIMDJSON_PADDING;
    return result;
#else
    return {};
#endif
}

void resetParseDiagnostics() noexcept {
#ifdef GAME_JSON_DIAGNOSTICS
    diagnostics = {};
#endif
}

class Decoder {
  public:
    static json decode(const simdjson::dom::element &element) {
        GAME_JSON_RECORD(valuesDecoded);
        switch (element.type()) {
        case simdjson::dom::element_type::ARRAY: {
            simdjson::dom::array array;
            checkParseError(element.get_array().get(array));
            json result = json::array();
            auto &values = std::get<json::array_t>(result.data);
            if (array.size() != 0) {
                values.reserve(array.size());
                GAME_JSON_RECORD(arrayGrowths);
            }
            for (auto child : array) {
                values.emplace_back(decode(child));
                GAME_JSON_RECORD(arrayAppends);
            }
            return result;
        }
        case simdjson::dom::element_type::OBJECT: {
            simdjson::dom::object object;
            checkParseError(element.get_object().get(object));
            json result = json::object();
            auto &fields = std::get<json::object_t>(result.data);
            for (simdjson::dom::key_value_pair field : object) {
                auto [entry, inserted] = fields.try_emplace(std::string(field.key));
                if (!inserted) {
                    throw std::runtime_error("duplicate JSON object key: " + entry->first);
                }
                GAME_JSON_RECORD(objectInsertions);
                entry->second = decode(field.value);
            }
            return result;
        }
        case simdjson::dom::element_type::STRING: {
            std::string_view value;
            checkParseError(element.get_string().get(value));
            return json(std::string(value));
        }
        case simdjson::dom::element_type::INT64: {
            std::int64_t value = 0;
            checkParseError(element.get_int64().get(value));
            return json(static_cast<long long>(value));
        }
        case simdjson::dom::element_type::UINT64: {
            std::uint64_t value = 0;
            checkParseError(element.get_uint64().get(value));
            return json(static_cast<unsigned long long>(value));
        }
        case simdjson::dom::element_type::DOUBLE: {
            double value = 0;
            checkParseError(element.get_double().get(value));
            return json(value);
        }
        case simdjson::dom::element_type::BOOL: {
            bool value = false;
            checkParseError(element.get_bool().get(value));
            return json(value);
        }
        case simdjson::dom::element_type::NULL_VALUE:
            return json(nullptr);
        case simdjson::dom::element_type::BIGINT: {
            std::string_view value;
            checkParseError(element.get_string().get(value));
            return json(std::string(value));
        }
        }
        return json(nullptr);
    }
};
} // namespace game::json_detail

namespace {
void appendEscapedString(std::ostringstream &stream, const std::string &value) {
    stream << '"';
    for (unsigned char ch : value) {
        switch (ch) {
        case '"':
            stream << "\\\"";
            break;
        case '\\':
            stream << "\\\\";
            break;
        case '\b':
            stream << "\\b";
            break;
        case '\f':
            stream << "\\f";
            break;
        case '\n':
            stream << "\\n";
            break;
        case '\r':
            stream << "\\r";
            break;
        case '\t':
            stream << "\\t";
            break;
        default:
            if (ch < 0x20) {
                stream << "\\u" << std::hex << std::setw(4) << std::setfill('0') << static_cast<int>(ch) << std::dec
                       << std::setfill(' ');
            } else {
                stream << static_cast<char>(ch);
            }
            break;
        }
    }
    stream << '"';
}

void appendIndent(std::ostringstream &stream, int count) {
    for (int i = 0; i < count; ++i) {
        stream << ' ';
    }
}

void appendDump(std::ostringstream &stream, const json &value, int indent, int depth) {
    if (value.is_null()) {
        stream << "null";
    } else if (value.is_string()) {
        appendEscapedString(stream, value.get<std::string>());
    } else if (value.is_boolean()) {
        stream << (value.get<bool>() ? "true" : "false");
    } else if (value.is_number_unsigned()) {
        stream << value.get<unsigned long long>();
    } else if (value.is_number_integer()) {
        stream << value.get<long long>();
    } else if (value.is_number()) {
        const double number = value.get<double>();
        if (!std::isfinite(number)) {
            stream << "null";
        } else {
            stream << std::setprecision(std::numeric_limits<double>::max_digits10) << number;
        }
    } else if (value.is_array()) {
        stream << '[';
        bool first = true;
        for (const auto &entry : value) {
            if (!first) {
                stream << ',';
            }
            if (indent >= 0) {
                stream << '\n';
                appendIndent(stream, (depth + 1) * indent);
            }
            appendDump(stream, entry, indent, depth + 1);
            first = false;
        }
        if (!first && indent >= 0) {
            stream << '\n';
            appendIndent(stream, depth * indent);
        }
        stream << ']';
    } else if (value.is_object()) {
        stream << '{';
        bool first = true;
        for (const auto &[key, entry] : value.items()) {
            if (!first) {
                stream << ',';
            }
            if (indent >= 0) {
                stream << '\n';
                appendIndent(stream, (depth + 1) * indent);
            }
            appendEscapedString(stream, key);
            stream << (indent >= 0 ? ": " : ":");
            appendDump(stream, entry, indent, depth + 1);
            first = false;
        }
        if (!first && indent >= 0) {
            stream << '\n';
            appendIndent(stream, depth * indent);
        }
        stream << '}';
    }
}
} // namespace

json::json() : data(nullptr) {}

json::json(std::nullptr_t) : data(nullptr) {}

json::json(const char *value) : data(std::string(value == nullptr ? "" : value)) {}

json::json(std::string value) : data(std::move(value)) {}

json::json(bool value) : data(value) {}

json::json(int value) : data(static_cast<std::int64_t>(value)) {}

json::json(unsigned int value) : data(static_cast<std::uint64_t>(value)) {}

json::json(long value) : data(static_cast<std::int64_t>(value)) {}

json::json(unsigned long value) : data(static_cast<std::uint64_t>(value)) {}

json::json(long long value) : data(static_cast<std::int64_t>(value)) {}

json::json(unsigned long long value) : data(static_cast<std::uint64_t>(value)) {}

json::json(double value) : data(value) {}

json::json(std::initializer_list<object_t::value_type> values) : data(object_t{}) {
    auto &object = std::get<object_t>(data);
    for (const auto &[key, value] : values) {
        object[key] = value;
    }
}

json json::object() {
    json value;
    value.data = object_t{};
    return value;
}

json json::array() {
    json value;
    value.data = array_t{};
    return value;
}

json json::array(std::initializer_list<json> values) {
    json value = json::array();
    auto &array = std::get<array_t>(value.data);
    array.assign(values.begin(), values.end());
    return value;
}

json json::parse(const char *text) { return parse(std::string_view(text == nullptr ? "" : text)); }

json json::parse(const std::string &text) { return parse(std::string_view(text)); }

json json::parse(std::string_view text) {
    ParseLease lease(text.size());
    auto &context = lease.get();
    context.prepare(text);
    simdjson::dom::element element;
    checkParseError(context.parser.parse(context.input.data(), text.size(), false).get(element));
    return game::json_detail::Decoder::decode(element);
}

bool json::is_null() const { return std::holds_alternative<std::nullptr_t>(data); }

bool json::is_object() const { return std::holds_alternative<object_t>(data); }

bool json::is_array() const { return std::holds_alternative<array_t>(data); }

bool json::is_string() const { return std::holds_alternative<std::string>(data); }

bool json::is_boolean() const { return std::holds_alternative<bool>(data); }

bool json::is_number() const {
    return std::holds_alternative<std::int64_t>(data) || std::holds_alternative<std::uint64_t>(data) ||
           std::holds_alternative<double>(data);
}

bool json::is_number_integer() const {
    return std::holds_alternative<std::int64_t>(data) || std::holds_alternative<std::uint64_t>(data);
}

bool json::is_number_unsigned() const { return std::holds_alternative<std::uint64_t>(data); }

bool json::empty() const { return size() == 0; }

std::size_t json::size() const {
    if (const auto object = objectPtr()) {
        return object->size();
    }
    if (const auto array = arrayPtr()) {
        return array->size();
    }
    if (is_string()) {
        return std::get<std::string>(data).size();
    }
    return 0;
}

std::size_t json::count(const std::string &key) const { return contains(key) ? 1 : 0; }

bool json::contains(const std::string &key) const {
    const auto object = objectPtr();
    return object != nullptr && object->find(key) != object->end();
}

json &json::operator[](const std::string &key) { return ensureObject()[key]; }

json &json::operator[](const char *key) { return (*this)[std::string(key == nullptr ? "" : key)]; }

const json &json::operator[](const std::string &key) const {
    const auto object = objectPtr();
    if (object == nullptr) {
        return nullValue();
    }
    auto iter = object->find(key);
    return iter == object->end() ? nullValue() : iter->second;
}

const json &json::operator[](const char *key) const { return (*this)[std::string(key == nullptr ? "" : key)]; }

json &json::operator[](int index) { return (*this)[static_cast<std::size_t>(index)]; }

const json &json::operator[](int index) const { return (*this)[static_cast<std::size_t>(index)]; }

json &json::operator[](unsigned int index) { return (*this)[static_cast<std::size_t>(index)]; }

const json &json::operator[](unsigned int index) const { return (*this)[static_cast<std::size_t>(index)]; }

json &json::operator[](std::size_t index) {
    auto &array = ensureArray();
    if (index >= array.size()) {
        array.resize(index + 1);
    }
    return array[index];
}

const json &json::operator[](std::size_t index) const {
    const auto array = arrayPtr();
    if (array == nullptr || index >= array->size()) {
        return nullValue();
    }
    return (*array)[index];
}

json &json::at(const std::string &key) {
    auto &object = ensureObject();
    return object.at(key);
}

const json &json::at(const std::string &key) const {
    const auto object = objectPtr();
    if (object == nullptr) {
        throw std::out_of_range("json value is not an object");
    }
    return object->at(key);
}

json &json::at(std::size_t index) { return ensureArray().at(index); }

const json &json::at(std::size_t index) const {
    const auto array = arrayPtr();
    if (array == nullptr) {
        throw std::out_of_range("json value is not an array");
    }
    return array->at(index);
}

void json::erase(const std::string &key) {
    if (auto object = std::get_if<object_t>(&data)) {
        object->erase(key);
    }
}

json::object_t &json::items() { return ensureObject(); }

const json::object_t &json::items() const {
    const auto object = objectPtr();
    return object == nullptr ? emptyObject() : *object;
}

json::array_t::iterator json::begin() { return ensureArray().begin(); }

json::array_t::iterator json::end() { return ensureArray().end(); }

json::array_t::const_iterator json::begin() const {
    const auto array = arrayPtr();
    return array == nullptr ? emptyArray().begin() : array->begin();
}

json::array_t::const_iterator json::end() const {
    const auto array = arrayPtr();
    return array == nullptr ? emptyArray().end() : array->end();
}

json::array_t::const_iterator json::cbegin() const { return begin(); }

json::array_t::const_iterator json::cend() const { return end(); }

std::string json::dump(int indent) const {
    std::ostringstream stream;
    appendDump(stream, *this, indent, 0);
    return stream.str();
}

json::object_t &json::ensureObject() {
    if (!is_object()) {
        data = object_t{};
    }
    return std::get<object_t>(data);
}

json::array_t &json::ensureArray() {
    if (!is_array()) {
        data = array_t{};
    }
    return std::get<array_t>(data);
}

const json::object_t *json::objectPtr() const { return std::get_if<object_t>(&data); }

const json::array_t *json::arrayPtr() const { return std::get_if<array_t>(&data); }

const json &json::nullValue() {
    static const json value(nullptr);
    return value;
}

const json::object_t &json::emptyObject() {
    static const object_t value;
    return value;
}

const json::array_t &json::emptyArray() {
    static const array_t value;
    return value;
}
