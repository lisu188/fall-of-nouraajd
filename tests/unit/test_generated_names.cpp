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

#include "core/CGeneratedName.h"
#include "core/CSerialization.h"
#include "object/CGameObject.h"
#include "test_harness.h"

#include <algorithm>
#include <array>
#include <atomic>
#include <cstdint>
#include <iostream>
#include <limits>
#include <locale>
#include <memory>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {

template <typename Unsigned> std::string legacyHex(Unsigned value) {
    std::stringstream stream;
    stream << std::hex << value;
    auto result = stream.str();
    for (char &digit : result) {
        if (digit >= 'a' && digit <= 'f') {
            digit -= 'a' - 'A';
        }
    }
    return result;
}

std::string legacyName(std::uintptr_t address, double randomDraw, std::uint64_t sequence) {
    return vstd::to_hex_hash(legacyHex(address), randomDraw, sequence);
}

class RestoreNameRng {
  public:
    ~RestoreNameRng() { vstd::rng() = previous; }

  private:
    std::mt19937_64 previous = vstd::rng();
};

void testHexAndNameFormattingMatchesLegacy() {
    constexpr std::array<std::uintptr_t, 6> addresses = {0,
                                                         1,
                                                         0xABCDEF,
                                                         0x10000000,
                                                         std::numeric_limits<std::uintptr_t>::max() / 2,
                                                         std::numeric_limits<std::uintptr_t>::max()};
    constexpr std::array<double, 7> draws = {
        0.0, -0.0, 0.25, -0.5, 0.5, std::numeric_limits<double>::lowest(), std::numeric_limits<double>::max()};
    constexpr std::array<std::uint64_t, 4> sequences = {0, 1, 0xABCDEF, std::numeric_limits<std::uint64_t>::max()};
    for (const auto address : addresses) {
        expect_true(generatedNameDetail::formatHex(address) == legacyHex(address),
                    "stack hex formatting preserves uppercase digits and omits leading zeroes at all pointer widths");
        for (const auto draw : draws) {
            for (const auto sequence : sequences) {
                expect_true(generatedNameDetail::formatProductionName(address, draw, sequence) ==
                                legacyName(address, draw, sequence),
                            "generated name formatting preserves legacy hash inputs, combination order and digits");
            }
        }
    }
    expect_true(generatedNameDetail::formatHex(std::uint64_t{0xABCDEF}) == "ABCDEF" &&
                    generatedNameDetail::formatHex(std::uint64_t{0}) == "0" &&
                    generatedNameDetail::formatHex(std::numeric_limits<std::uint64_t>::max()) == "FFFFFFFFFFFFFFFF",
                "hex formatting preserves the explicit zero, uppercase and full-width contracts");
}

void testProductionNamesPreserveDrawsAndCollisionSequence() {
    RestoreNameRng restoreRng;
    const auto object = std::make_shared<CGameObject>();
    const auto address = reinterpret_cast<std::uintptr_t>(object.get());
    constexpr std::array<std::uint32_t, 4> seeds = {0, 1, 100, std::numeric_limits<std::uint32_t>::max()};
    for (const auto seed : seeds) {
        CSerialization::NameFixtureScopeForTests production;
        vstd::rng().seed(seed);
        std::vector<std::string> expected;
        for (std::uint64_t sequence = 0; sequence < 6; ++sequence) {
            expected.push_back(legacyName(address, vstd::rand(), sequence));
        }
        const auto expectedRng = vstd::rng();
        vstd::rng().seed(seed);
        for (std::size_t index = 0; index < 2; ++index) {
            expect_true(CSerialization::generateName(object) == expected[index],
                        "production names preserve the legacy result for every seeded draw");
        }
        std::vector<std::string> candidates;
        const auto accepted = CSerialization::generateName(object, [&](const std::string &candidate) {
            candidates.push_back(candidate);
            return candidates.size() < 4;
        });
        expect_true(candidates == std::vector<std::string>(expected.begin() + 2, expected.end()) &&
                        accepted == expected.back(),
                    "production collision retries preserve exact candidate order and sequence increments");
        expect_true(vstd::rng() == expectedRng,
                    "production name calls and retries preserve the complete random generator state");

        const auto beforeExhaustion = vstd::rng();
        expected.clear();
        for (std::uint64_t sequence = 6; sequence < 262; ++sequence) {
            expected.push_back(legacyName(address, vstd::rand(), sequence));
        }
        const auto afterExhaustion = vstd::rng();
        vstd::rng() = beforeExhaustion;
        candidates.clear();
        bool threw = false;
        try {
            CSerialization::generateName(object, [&](const std::string &candidate) {
                candidates.push_back(candidate);
                return true;
            });
        } catch (const std::runtime_error &) {
            threw = true;
        }
        expect_true(threw && candidates == expected && vstd::rng() == afterExhaustion,
                    "production collision exhaustion preserves all 256 legacy attempts and random draws");
        const auto beforeNext = vstd::rng();
        const auto expectedNext = legacyName(address, vstd::rand(), 262);
        vstd::rng() = beforeNext;
        expect_true(CSerialization::generateName(object) == expectedNext,
                    "production name sequence continues after exhausted retries");
    }
}

class CountingIntegerOutput : public std::num_put<char> {
  public:
    explicit CountingIntegerOutput(std::shared_ptr<std::atomic<std::size_t>> count)
        : count(std::move(count)), owner(std::this_thread::get_id()) {}

  protected:
    iter_type do_put(iter_type output, std::ios_base &stream, char_type fill, unsigned long value) const override {
        countCall();
        return std::num_put<char>::do_put(output, stream, fill, value);
    }

    iter_type do_put(iter_type output, std::ios_base &stream, char_type fill, unsigned long long value) const override {
        countCall();
        return std::num_put<char>::do_put(output, stream, fill, value);
    }

  private:
    void countCall() const {
        if (std::this_thread::get_id() == owner) {
            ++*count;
        }
    }

    std::shared_ptr<std::atomic<std::size_t>> count;
    std::thread::id owner;
};

class RestoreGlobalLocale {
  public:
    explicit RestoreGlobalLocale(const std::locale &locale) : previous(std::locale::global(locale)) {}
    ~RestoreGlobalLocale() { std::locale::global(previous); }

  private:
    std::locale previous;
};

void testGeneratedNamesAvoidNumericStreamFormatting() {
    constexpr std::size_t nameCount = 64;
    RestoreNameRng restoreRng;
    CSerialization::NameFixtureScopeForTests production;
    const auto object = std::make_shared<CGameObject>();
    const auto address = reinterpret_cast<std::uintptr_t>(object.get());
    auto count = std::make_shared<std::atomic<std::size_t>>(0);
    std::size_t legacyCalls = 0;
    std::size_t actualCalls = 0;
    std::vector<std::string> expected;
    std::vector<std::string> actual;
    expected.reserve(nameCount);
    actual.reserve(nameCount);
    {
        RestoreGlobalLocale restoreLocale(std::locale(std::locale(), new CountingIntegerOutput(count)));
        vstd::rng().seed(100);
        for (std::uint64_t sequence = 0; sequence < nameCount; ++sequence) {
            expected.push_back(legacyName(address, vstd::rand(), sequence));
        }
        legacyCalls = count->exchange(0);
        vstd::rng().seed(100);
        for (std::size_t index = 0; index < nameCount; ++index) {
            actual.push_back(CSerialization::generateName(object));
        }
        actualCalls = count->load();
    }
    expect_true(legacyCalls == nameCount * 2,
                "generated-name stream guard detects both legacy integer formatting operations per name");
    expect_true(actual == expected && actualCalls == 0,
                "production generated names preserve output with zero numeric stream formatting operations");
    std::cout << "generated name formatting guard: names=" << nameCount << " legacy-stream-calls=" << legacyCalls
              << " actual-stream-calls=" << actualCalls << " budget=0\n";
}

} // namespace

void run_generated_name_tests() {
    testHexAndNameFormattingMatchesLegacy();
    testProductionNamesPreserveDrawsAndCollisionSequence();
}

void run_generated_name_performance_tests() { testGeneratedNamesAvoidNumericStreamFormatting(); }
