/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026 Andrzej Lis
SPDX-License-Identifier: GPL-3.0-or-later
*/

#include <string>

namespace {
std::string profileDirectory;
}

#define GAME_NATIVE_TEST_PROFILE_DIR profileDirectory
#include "native_test_profile.h"
#include <cstdlib>
#include <stdexcept>

int main(int argc, char **argv) {
    if (argc != 3) {
        std::cerr << "Usage: native_test_profile_fixture MODE OUTPUT_DIRECTORY\n";
        return 2;
    }
    const std::string mode = argv[1];
    profileDirectory = argv[2];
    CNativeTestProfile profile("fixture");
    if (mode == "interrupt") {
        profile.run("interrupted", [] { std::_Exit(23); });
    }
    if (mode == "return-code") {
        return profile.run("return-code", [] { return 17; });
    }
    if (mode == "sampling-batches") {
        int samples = 0;
        profile.run("unchanged-sampling", [&] {
            for (const char *batch : {"full-budget", "tight-budget", "player-exclusion"}) {
                profile.run(batch, [&] {
                    for (int attempt = 0; attempt < 256; ++attempt) {
                        ++samples;
                    }
                });
            }
        });
        return samples == 768 ? 0 : 5;
    }
    int calls = 0;
    const int result = profile.run("outer", [&] {
        return profile.run("setup", [&] {
            ++calls;
            return 42;
        });
    });
    if (result != 42 || calls != 1) {
        return 1;
    }
    int value = 4;
    int &reference = profile.run("reference", [&]() -> int & { return value; });
    reference += 2;
    if (value != 6) {
        return 2;
    }
    try {
        profile.run("throws", [] { throw std::runtime_error("original exception"); });
        return 3;
    } catch (const std::runtime_error &error) {
        if (std::string(error.what()) != "original exception") {
            return 4;
        }
    }
    if (mode == "success") {
        profile.run("flush", [&] {
            std::ifstream input(std::filesystem::path(GAME_NATIVE_TEST_PROFILE_DIR) / "fixture.tsv");
            std::string line;
            std::string last;
            while (std::getline(input, line)) {
                last = line;
            }
            if (last.find("\tSTART\tflush\t") == std::string::npos) {
                throw std::runtime_error("START was not flushed before its action");
            }
        });
    }
    return 0;
}
