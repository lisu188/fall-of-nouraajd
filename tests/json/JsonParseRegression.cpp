/* Copyright (C) 2026 Andrzej Lis. Licensed under GPL-3.0-or-later. */
#include "LegacyJsonParser.h"
#include "core/CJsonParseDiagnostics.h"

#include <atomic>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <new>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {
thread_local bool parse_on_allocation = false;
thread_local bool nested_parse_passed = false;
} // namespace

void *operator new(std::size_t size) {
    void *result = std::malloc(size == 0 ? 1 : size);
    if (!result) {
        throw std::bad_alloc();
    }
    if (parse_on_allocation) {
        parse_on_allocation = false;
        try {
            nested_parse_passed = json::parse("{\"nested\":true}").at("nested").get<bool>();
        } catch (...) {
            nested_parse_passed = false;
        }
    }
    return result;
}
void *operator new[](std::size_t size) { return ::operator new(size); }
void operator delete(void *value) noexcept { std::free(value); }
void operator delete[](void *value) noexcept { std::free(value); }
void operator delete(void *value, std::size_t) noexcept { std::free(value); }
void operator delete[](void *value, std::size_t) noexcept { std::free(value); }

namespace {
void require(bool condition, const std::string &message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

void compareValues(const json &expected, const json &actual) {
    require(expected.is_null() == actual.is_null(), "null type differs");
    require(expected.is_object() == actual.is_object(), "object type differs");
    require(expected.is_array() == actual.is_array(), "array type differs");
    require(expected.is_string() == actual.is_string(), "string type differs");
    require(expected.is_boolean() == actual.is_boolean(), "boolean type differs");
    require(expected.is_number_integer() == actual.is_number_integer(), "integer type differs");
    require(expected.is_number() == actual.is_number(), "number type differs");
    require(expected.size() == actual.size(), "size differs");
    if (expected.is_object()) {
        for (const auto &[key, value] : expected.items()) {
            require(actual.contains(key), "missing decoded key");
            compareValues(value, actual.at(key));
        }
    } else if (expected.is_array()) {
        for (std::size_t i = 0; i < expected.size(); ++i) {
            compareValues(expected.at(i), actual.at(i));
        }
    } else if (expected.is_string()) {
        require(expected.get<std::string>() == actual.get<std::string>(), "string differs");
    } else if (expected.is_boolean()) {
        require(expected.get<bool>() == actual.get<bool>(), "boolean differs");
    } else if (expected.is_number_integer()) {
        require(expected.get<long long>() == actual.get<long long>(), "signed integer view differs");
        require(expected.get<unsigned long long>() == actual.get<unsigned long long>(), "unsigned view differs");
        require(expected.get<double>() == actual.get<double>(), "integer signedness differs");
    } else if (expected.is_number()) {
        const auto lhs = expected.get<double>();
        const auto rhs = actual.get<double>();
        require(std::memcmp(&lhs, &rhs, sizeof(lhs)) == 0, "floating bits differ");
    }
}

bool compareInput(std::string_view input) {
    bool legacy_accepted = false;
    bool current_accepted = false;
    json expected;
    json actual;
    try {
        expected = legacyJsonParse(input);
        legacy_accepted = true;
    } catch (const std::exception &) {
    }
    try {
        actual = json::parse(input);
        current_accepted = true;
    } catch (const std::exception &error) {
        const std::string message(error.what());
        require(message.find("JSON") != std::string::npos, "parse failure lost JSON error context");
    }
    require(legacy_accepted == current_accepted,
            "DOM compatibility differs for input prefix: " + std::string(input.substr(0, 100)));
    if (legacy_accepted) {
        compareValues(expected, actual);
    }
    return legacy_accepted;
}

std::string nested(std::size_t ancestors, std::string leaf, bool object) {
    std::string text;
    for (std::size_t i = 0; i < ancestors; ++i) {
        text += object ? "{\"a\":" : "[";
    }
    text += leaf;
    text.append(ancestors, object ? '}' : ']');
    return text;
}

void regressionTests() {
    const std::vector<std::string> examples = {"null",
                                               "true",
                                               "false",
                                               "0",
                                               "-0",
                                               "-0.0",
                                               "1.5",
                                               "-2.125",
                                               "1e-300",
                                               "1e308",
                                               "1e-9999",
                                               "9223372036854775807",
                                               "9223372036854775808",
                                               "18446744073709551615",
                                               "-9223372036854775808",
                                               "18446744073709551616",
                                               "-9223372036854775809",
                                               "1e309",
                                               "01",
                                               "-01",
                                               "+1",
                                               "1.",
                                               ".1",
                                               "1e",
                                               "-",
                                               "\"\"",
                                               "\"Hello \\u00e9 \\ud83d\\ude00\"",
                                               "\"a\\u0000b\"",
                                               "\"a\\n\\t\\\\\\\"b\"",
                                               "[]",
                                               "{}",
                                               "[1,true,null,\"x\",{},[]]",
                                               "{\"z\":[1,2],\"a\":{\"key\":false}}",
                                               "{\"a\":1,\"a\":2}",
                                               "{\"a\":1,\"\\u0061\":2}",
                                               "{\"a\\u0000b\":1,\"a\":2}",
                                               "{\"a\\u0000b\":1,\"a\\u0000b\":2}",
                                               "[1,]",
                                               "{\"a\":1,}",
                                               "[1 2]",
                                               "{\"a\" 1}",
                                               "{\"a\":tru}",
                                               "[falsee]",
                                               "\"\\uD800\"",
                                               "\"\\uDC00\"",
                                               "\"\\x41\"",
                                               "\"unterminated",
                                               "",
                                               " \n\t\r",
                                               "\v[]",
                                               "[] trailing",
                                               "{}{}",
                                               "true false",
                                               "1 2",
                                               "\"x\"[]",
                                               "null x",
                                               "[0,{\"late\":[1,2,\"\\uD800\"]}]",
                                               "[0,{\"late\":[1,2,01]}]",
                                               "{\"late\":[1,2,]}",
                                               std::string("\xef\xbb\xbf") + "{\"bom\":true}",
                                               " \n\t\r[1] \n\t\r",
                                               std::string("\"a\0b\"", 5),
                                               std::string("[1]\0[]", 6),
                                               std::string("\"\xc0\xaf\"", 4),
                                               std::string("{\"\xed\xa0\x80\":1}", 9)};
    for (const auto &text : examples) {
        compareInput(text);
    }
    for (bool object : {false, true}) {
        require(compareInput(nested(1023, "0", object)), "1023 nonempty containers must parse");
        require(!compareInput(nested(1024, "0", object)), "1024 nonempty containers must fail");
        require(compareInput(nested(1023, "[]", object)), "empty array at depth limit must parse");
        require(compareInput(nested(1023, "{}", object)), "empty object at depth limit must parse");
        require(!compareInput(nested(1024, "[]", object)), "too-deep empty leaf must fail");
    }
    const std::string complete = "{\"string\":\"escape \\ud83d\\ude00\",\"array\":[null,1,true,{}]}";
    for (std::size_t length = 0; length < complete.size(); ++length) {
        compareInput(std::string_view(complete.data(), length));
    }
    std::string input = "{\"owned\":\"original\",\"nested\":[{\"key\":\"value\"}]}";
    auto retained = json::parse(input);
    input.assign(input.size(), 'x');
    for (int i = 0; i < 20; ++i) {
        compareInput(i % 2 ? "[1,2,3]" : "{\"broken\":[] trailing}");
    }
    require(retained.at("owned").get<std::string>() == "original", "input buffer ownership lost");
    require(retained.at("nested").at(0).at("key").get<std::string>() == "value", "parser buffer ownership lost");
    std::string large = "[\"" + std::string(4 * 1024 * 1024 + 1, 'x') + "\"]";
    require(compareInput(large), "oversized valid input rejected");
    compareInput("{\"afterLarge\":true}");
}

void concurrencyTests() {
    std::atomic<bool> passed{true};
    std::vector<std::thread> workers;
    for (int thread = 0; thread < 4; ++thread) {
        workers.emplace_back([thread, &passed]() {
            try {
                for (int i = 0; i < 100; ++i) {
                    compareInput("{\"thread\":" + std::to_string(thread) + ",\"value\":[1,2,3]}");
                    compareInput("[1,broken]");
                }
            } catch (...) {
                passed = false;
            }
        });
    }
    for (auto &worker : workers) {
        worker.join();
    }
    require(passed, "concurrent parsing failed");
}

void reentrantTest() {
    using namespace game::json_detail;
    const std::string text = "{\"outer\":[\"owned\"]}";
    json::parse(text);
    resetParseDiagnostics();
    nested_parse_passed = false;
    parse_on_allocation = true;
    const auto outer = json::parse(text);
    parse_on_allocation = false;
    const auto counters = parseDiagnostics();
    require(nested_parse_passed, "reentrant parse during allocation failed");
    require(outer.at("outer").at(0).get<std::string>() == "owned", "reentrant parse corrupted outer value");
    require(counters.temporaryContexts == 1, "reentrant parse must use a temporary context");
}

void performanceGuards() {
    using namespace game::json_detail;
    const std::string text = "{\"a\":[1,2,3],\"b\":{\"c\":true,\"d\":\"owned\"}}";
    json::parse(text);
    resetParseDiagnostics();
    for (int i = 0; i < 32; ++i) {
        json::parse(text);
    }
    auto counters = parseDiagnostics();
    require(counters.parserCreations == 0 && counters.parserGrowths == 0 && counters.scratchGrowths == 0,
            "warm parsing allocated parser or input scratch");
    require(counters.valuesDecoded == 8 * 32, "values must be decoded exactly once");
    require(counters.arrayAppends == 3 * 32, "arrays must append each child exactly once");
    require(counters.objectInsertions == 4 * 32, "objects must insert each key exactly once");
    std::string array = "[0";
    for (int i = 1; i < 4096; ++i) {
        array += ",0";
    }
    array += "]";
    json::parse(array);
    resetParseDiagnostics();
    auto parsed = json::parse(array);
    counters = parseDiagnostics();
    require(parsed.size() == 4096 && counters.valuesDecoded == 4097, "array traversal budget differs");
    require(counters.arrayAppends == 4096, "array append budget differs");
    require(counters.arrayGrowths == 1, "DOM array conversion must reserve exactly once");
    require(counters.parserGrowths == 0 && counters.scratchGrowths == 0, "warmed large array grew scratch");
    const auto retained_capacity = counters.retainedCapacity;
    std::string large = "\"" + std::string(4 * 1024 * 1024 + 1, 'z') + "\"";
    resetParseDiagnostics();
    require(json::parse(large).size() == large.size() - 2, "oversized string did not parse");
    counters = parseDiagnostics();
    require(counters.temporaryContexts == 1, "oversized parsing must use a temporary context");
    require(counters.retainedCapacity == retained_capacity, "oversized parsing grew retained capacity");
    require(counters.retainedCapacity <= 4 * 1024 * 1024, "retained input capacity exceeds 4 MiB");
    std::cout << "performance guards: warm parser/scratch growth=0; one "
                 "decode/value; 4096 entries reserved once; "
                 "oversized context temporary; retained capacity="
              << counters.retainedCapacity << '\n';
}
} // namespace

int main(int argc, char **argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--performance") {
            performanceGuards();
        } else {
            // A null C-string is parsed as empty input and must throw, matching the
            // existing API.
            bool threw = false;
            try {
                json::parse(static_cast<const char *>(nullptr));
            } catch (const std::exception &) {
                threw = true;
            }
            require(threw, "null C-string unexpectedly parsed");
            regressionTests();
            concurrencyTests();
            reentrantTest();
            std::cout << "DOM oracle compatibility, depth boundaries, ownership, "
                         "recovery, concurrency and reentrancy passed\n";
        }
        return 0;
    } catch (const std::exception &error) {
        std::cerr << "JSON regression failed: " << error.what() << '\n';
        return 1;
    }
}
