/* Copyright (C) 2026 Andrzej Lis. Licensed under GPL-3.0-or-later. */
#include "LegacyJsonParser.h"
#include "core/CJsonParseDiagnostics.h"

#include <atomic>
#include <charconv>
#include <cstdint>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <limits>
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

void integerDumpTests() {
    const auto fitsNativeInt = [](const json &value) {
        if (!value.is_number_integer())
            return false;
        const auto encoded = value.dump();
        int native = 0;
        const auto parsed = std::from_chars(encoded.data(), encoded.data() + encoded.size(), native);
        return parsed.ec == std::errc{} && parsed.ptr == encoded.data() + encoded.size();
    };
    for (const auto *text : {"9223372036854775808", "18446744073709551615"}) {
        const auto value = json::parse(text);
        require(value.is_number_integer() && value.is_number_unsigned(), "wide positive integer lost unsigned storage");
        require(value.dump() == text, "wide unsigned integer changed sign during dump");
        require(json::parse(value.dump()).get<unsigned long long>() == value.get<unsigned long long>(),
                "wide unsigned integer changed value during round trip");
        const json nested = {{"authority", value}, {"values", json::array({value})}};
        const auto restored = json::parse(nested.dump(2));
        require(restored.at("authority").dump() == text && restored.at("values").at(0).dump() == text,
                "nested unsigned integer lost its spelling");
        require(!fitsNativeInt(value), "wide unsigned integer aliased a signed native authority value");
    }
    const auto maximum = std::numeric_limits<std::uint64_t>::max();
    require(json(static_cast<unsigned long long>(maximum)).dump() == "18446744073709551615",
            "constructed maximum unsigned integer changed sign");
    for (int choice = 1; choice <= 20; ++choice) {
        const auto ordinary = json(choice);
        require(!ordinary.is_number_unsigned() && ordinary.dump() == std::to_string(choice) && fitsNativeInt(ordinary),
                "ordinary native choice integer changed");
        const auto wide = json(static_cast<unsigned long long>(maximum - static_cast<std::uint64_t>(choice - 1)));
        require(wide.is_number_unsigned() && !fitsNativeInt(wide),
                "wide integer must not enter the signed native range before choice bounds are applied");
    }
    for (const auto *text :
         {"-9223372036854775808", "-2147483648", "-20", "-1", "0", "2147483647", "9223372036854775807"}) {
        const auto value = json::parse(text);
        require(value.is_number_integer() && !value.is_number_unsigned(), "signed integer changed storage category");
        require(value.dump() == text, "signed integer changed spelling");
        require(json::parse(value.dump()).get<long long>() == value.get<long long>(),
                "signed integer changed value during round trip");
    }
    require(fitsNativeInt(json(std::numeric_limits<int>::min())) &&
                fitsNativeInt(json(std::numeric_limits<int>::max())),
            "signed native endpoints changed");
    for (const auto *text : {"2147483648", "-2147483649", "4294967297", "-4294967295"})
        require(!fitsNativeInt(json::parse(text)), "out-of-range authority integer became a native int");
    for (const auto &value : {json(nullptr), json(true), json(1.5), json("1")})
        require(!value.is_number_unsigned() && !fitsNativeInt(value), "non-integer value gained integer authority");
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
    const std::string unsignedText =
        R"({"choices":[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20],)"
        R"("maximum":18446744073709551615,"negative":-2147483648,"nextSigned":9223372036854775808})";
    const auto unsignedDocument = json::parse(unsignedText);
    const auto unsignedCapacity = parseDiagnostics().retainedCapacity;
    constexpr int unsignedRounds = 32;
    std::size_t unsignedBytes = 0;
    resetParseDiagnostics();
    for (int round = 0; round < unsignedRounds; ++round) {
        const auto encoded = unsignedDocument.dump();
        require(encoded == unsignedText && encoded.size() == 151, "unsigned dump exceeded fixed output work");
        unsignedBytes += encoded.size();
        const auto restored = json::parse(encoded);
        require(restored.at("maximum").is_number_unsigned() &&
                    restored.at("maximum").get<unsigned long long>() == std::numeric_limits<std::uint64_t>::max() &&
                    restored.at("nextSigned").is_number_unsigned() &&
                    restored.at("nextSigned").get<unsigned long long>() == 9223372036854775808ULL &&
                    restored.at("negative").get<long long>() == -2147483648LL,
                "unsigned round trip lost integer identity");
    }
    counters = parseDiagnostics();
    require(unsignedBytes == 151 * unsignedRounds && counters.valuesDecoded == 25 * unsignedRounds &&
                counters.arrayAppends == 20 * unsignedRounds && counters.objectInsertions == 4 * unsignedRounds &&
                counters.arrayGrowths == unsignedRounds,
            "unsigned round-trip traversal or output budget differs");
    require(counters.parserCreations == 0 && counters.parserGrowths == 0 && counters.scratchGrowths == 0 &&
                counters.temporaryContexts == 0 && counters.retainedCapacity == unsignedCapacity,
            "warmed unsigned round trips grew parser storage or used temporary contexts");
    std::cout << "performance guards: unsigned round trips=" << unsignedRounds << "; output bytes=" << unsignedBytes
              << "; decoded values=" << counters.valuesDecoded << "; array appends=" << counters.arrayAppends
              << "; object insertions=" << counters.objectInsertions << "; array reserves=" << counters.arrayGrowths
              << '\n';
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
            integerDumpTests();
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
