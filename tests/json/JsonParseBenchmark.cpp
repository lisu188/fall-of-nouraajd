/* Copyright (C) 2026 Andrzej Lis. Licensed under GPL-3.0-or-later. */
#include "LegacyJsonParser.h"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <iterator>
#include <new>
#include <string>
#include <vector>
#ifdef _WIN32
#include <psapi.h>
#include <windows.h>
#else
#include <sys/resource.h>
#endif

namespace {
thread_local bool count_allocations = false;
thread_local std::size_t allocation_count = 0;
thread_local std::size_t allocation_bytes = 0;
} // namespace

void *operator new(std::size_t size) {
    if (void *result = std::malloc(size == 0 ? 1 : size)) {
        if (count_allocations) {
            ++allocation_count;
            allocation_bytes += size;
        }
        return result;
    }
    throw std::bad_alloc();
}
void *operator new[](std::size_t size) { return ::operator new(size); }
void operator delete(void *value) noexcept { std::free(value); }
void operator delete[](void *value) noexcept { std::free(value); }
void operator delete(void *value, std::size_t) noexcept { std::free(value); }
void operator delete[](void *value, std::size_t) noexcept { std::free(value); }

namespace {
std::size_t peakRssBytes() {
#ifdef _WIN32
    PROCESS_MEMORY_COUNTERS counters{};
    if (GetProcessMemoryInfo(GetCurrentProcess(), &counters, static_cast<DWORD>(sizeof(counters)))) {
        return counters.PeakWorkingSetSize;
    }
    return 0;
#else
    struct rusage usage {};
    if (getrusage(RUSAGE_SELF, &usage) != 0) {
        return 0;
    }
#ifdef __APPLE__
    return static_cast<std::size_t>(usage.ru_maxrss);
#else
    return static_cast<std::size_t>(usage.ru_maxrss) * 1024;
#endif
#endif
}

void hashBytes(std::uint64_t &hash, const void *data, std::size_t size) {
    const auto *bytes = static_cast<const unsigned char *>(data);
    for (std::size_t i = 0; i < size; ++i) {
        hash = (hash ^ bytes[i]) * 1099511628211ULL;
    }
}
void hashValue(std::uint64_t &hash, const json &value) {
    const char tag = value.is_object()           ? 'o'
                     : value.is_array()          ? 'a'
                     : value.is_string()         ? 's'
                     : value.is_boolean()        ? 'b'
                     : value.is_number_integer() ? 'i'
                     : value.is_number()         ? 'd'
                                                 : 'n';
    hashBytes(hash, &tag, 1);
    if (value.is_object()) {
        for (const auto &[key, child] : value.items()) {
            hashBytes(hash, key.data(), key.size());
            hashValue(hash, child);
        }
    } else if (value.is_array()) {
        for (const auto &child : value) {
            hashValue(hash, child);
        }
    } else if (value.is_string()) {
        const auto text = value.get<std::string>();
        hashBytes(hash, text.data(), text.size());
    } else if (value.is_number_integer()) {
        const auto number = value.get<unsigned long long>();
        hashBytes(hash, &number, sizeof(number));
    } else if (value.is_number()) {
        const auto number = value.get<double>();
        hashBytes(hash, &number, sizeof(number));
    } else if (value.is_boolean()) {
        const char boolean = value.get<bool>() ? 't' : 'f';
        hashBytes(hash, &boolean, 1);
    }
    const char end = ';';
    hashBytes(hash, &end, 1);
}

struct RunResult {
    std::size_t accepted = 0;
    std::size_t rejected = 0;
    std::size_t checksum = 0;
};
RunResult runCorpus(const std::vector<std::string> &corpus, bool baseline, std::size_t rounds) {
    RunResult result;
    for (std::size_t round = 0; round < rounds; ++round) {
        for (const auto &input : corpus) {
            try {
                auto value = baseline ? legacyJsonParse(input) : json::parse(input);
                result.checksum += value.size();
                ++result.accepted;
            } catch (const std::exception &) {
                ++result.rejected;
            }
        }
    }
    return result;
}
} // namespace

int main(int argc, char **argv) {
    try {
        bool baseline = false;
        bool cold = false;
        std::size_t rounds = 1;
        std::size_t samples = 9;
        std::string list_path;
        for (int i = 1; i < argc; ++i) {
            const std::string option(argv[i]);
            if (option == "--mode" && i + 1 < argc) {
                const std::string mode(argv[++i]);
                if (mode != "baseline" && mode != "candidate") {
                    throw std::runtime_error("mode must be baseline or candidate");
                }
                baseline = mode == "baseline";
            } else if (option == "--rounds" && i + 1 < argc) {
                rounds = std::stoull(argv[++i]);
            } else if (option == "--samples" && i + 1 < argc) {
                samples = std::stoull(argv[++i]);
            } else if (option == "--file-list" && i + 1 < argc) {
                list_path = argv[++i];
            } else if (option == "--cold") {
                cold = true;
            } else {
                throw std::runtime_error("usage: json_parse_benchmark --file-list PATH "
                                         "--mode baseline|candidate "
                                         "[--rounds N] [--samples N] [--cold]");
            }
        }
        if (list_path.empty() || rounds == 0 || samples == 0 || (cold && (samples != 1 || rounds != 1))) {
            throw std::runtime_error("file list, positive counts and cold samples=rounds=1 required");
        }
        std::ifstream list(list_path);
        if (!list) {
            throw std::runtime_error("cannot open corpus file list");
        }
        std::vector<std::string> corpus;
        std::size_t corpus_bytes = 0;
        std::string path;
        while (std::getline(list, path)) {
            if (path.empty()) {
                continue;
            }
            std::ifstream file(path, std::ios::binary);
            if (!file) {
                throw std::runtime_error("cannot open corpus input: " + path);
            }
            corpus.emplace_back(std::istreambuf_iterator<char>(file), std::istreambuf_iterator<char>());
            corpus_bytes += corpus.back().size();
        }
        if (corpus.empty()) {
            throw std::runtime_error("corpus is empty");
        }
        std::vector<double> durations;
        std::vector<std::size_t> allocations;
        std::vector<std::size_t> allocated_bytes;
        durations.reserve(samples);
        allocations.reserve(samples);
        allocated_bytes.reserve(samples);
        if (!cold) {
            runCorpus(corpus, baseline, 1);
        }
        RunResult result;
        for (std::size_t sample = 0; sample < samples; ++sample) {
            allocation_count = 0;
            allocation_bytes = 0;
            count_allocations = true;
            const auto start = std::chrono::steady_clock::now();
            result = runCorpus(corpus, baseline, rounds);
            const auto stop = std::chrono::steady_clock::now();
            count_allocations = false;
            durations.push_back(std::chrono::duration<double, std::milli>(stop - start).count());
            allocations.push_back(allocation_count);
            allocated_bytes.push_back(allocation_bytes);
        }
        std::cout << "{\"mode\":\"" << (baseline ? "baseline" : "candidate")
                  << "\",\"cold\":" << (cold ? "true" : "false") << ",\"corpus_files\":" << corpus.size()
                  << ",\"corpus_bytes\":" << corpus_bytes << ",\"rounds\":" << rounds
                  << ",\"accepted_per_round\":" << result.accepted / rounds
                  << ",\"rejected_per_round\":" << result.rejected / rounds << ",\"checksum\":" << result.checksum
                  << ",\"peak_rss_bytes\":" << peakRssBytes() << ",\"sample_ms\":[";
        for (std::size_t i = 0; i < durations.size(); ++i) {
            std::cout << (i ? "," : "") << durations[i];
        }
        std::cout << "],\"cpp_allocations\":[";
        for (std::size_t i = 0; i < allocations.size(); ++i) {
            std::cout << (i ? "," : "") << allocations[i];
        }
        std::cout << "],\"cpp_allocated_bytes\":[";
        for (std::size_t i = 0; i < allocated_bytes.size(); ++i) {
            std::cout << (i ? "," : "") << allocated_bytes[i];
        }
        std::cout << "],\"corpus_results\":[";
        for (std::size_t i = 0; i < corpus.size(); ++i) {
            bool accepted = false;
            std::uint64_t fingerprint = 14695981039346656037ULL;
            try {
                const auto value = baseline ? legacyJsonParse(corpus[i]) : json::parse(corpus[i]);
                hashValue(fingerprint, value);
                accepted = true;
            } catch (const std::exception &) {
            }
            std::cout << (i ? "," : "") << "{\"accepted\":" << (accepted ? "true" : "false")
                      << ",\"owning_tree_fingerprint\":\"" << fingerprint << "\"}";
        }
        std::cout << "]}\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
