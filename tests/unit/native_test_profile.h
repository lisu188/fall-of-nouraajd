/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026  Andrzej Lis
SPDX-License-Identifier: GPL-3.0-or-later
*/

#pragma once

#include <chrono>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>
#include <string>
#include <type_traits>
#include <utility>

class CNativeTestProfile {
  public:
    explicit CNativeTestProfile(const char *suite) : suite(suite) {
        const auto directory = std::filesystem::path(GAME_NATIVE_TEST_PROFILE_DIR);
        std::error_code error;
        std::filesystem::create_directories(directory, error);
        if (!error) {
            output.open(directory / (this->suite + ".tsv"), std::ios::trunc);
        }
        if (output.is_open()) {
            output << "suite\tevent\tname\twallMs\tcpuMs\n" << std::flush;
        } else {
            std::cerr << "Native test profiling file is unavailable for " << suite << " in " << directory << '\n';
        }
    }

    template <typename Action> auto run(const char *name, Action &&action) -> std::invoke_result_t<Action> {
        Measurement measurement(*this, name);
        if constexpr (std::is_void_v<std::invoke_result_t<Action>>) {
            std::invoke(std::forward<Action>(action));
            measurement.complete();
        } else {
            decltype(auto) result = std::invoke(std::forward<Action>(action));
            measurement.complete();
            return result;
        }
    }

  private:
    class Measurement {
      public:
        Measurement(CNativeTestProfile &profile, const char *name)
            : profile(profile), name(name), started(std::chrono::steady_clock::now()), cpuStarted(cpuClock()) {
            profile.write("START", name, 0, 0);
        }

        ~Measurement() {
            if (!completed) {
                finish("EXCEPTION");
            }
        }

        void complete() {
            completed = true;
            finish("DONE");
        }

      private:
        static std::clock_t cpuClock() {
#ifdef _WIN32
            // MSVC clock measures elapsed wall time rather than process CPU.
            return std::clock_t(-1);
#else
            return std::clock();
#endif
        }

        void finish(const char *event) {
            const auto elapsed = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - started);
            const auto cpuEnded = cpuClock();
            const double cpu = cpuStarted == std::clock_t(-1) || cpuEnded == std::clock_t(-1)
                                   ? -1
                                   : 1000.0 * static_cast<double>(cpuEnded - cpuStarted) / CLOCKS_PER_SEC;
            profile.write(event, name, elapsed.count(), cpu);
        }

        CNativeTestProfile &profile;
        const char *name;
        std::chrono::steady_clock::time_point started;
        std::clock_t cpuStarted;
        bool completed = false;
    };

    void write(const char *event, const char *name, double wallMs, double cpuMs) {
        output << suite << '\t' << event << '\t' << name << '\t' << wallMs << '\t' << cpuMs << '\n' << std::flush;
    }

    std::string suite;
    std::ofstream output;
};
