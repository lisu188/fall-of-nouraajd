/*
 * MIT License
 *
 * Copyright (c) 2019 Andrzej Lis
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */
#pragma once

#include <string>
#include <sstream>
#include <iostream>
#include <fstream>
#include <memory>
#include <mutex>
#include "vdefines.h"
#include "vstring.h"

namespace vstd {
    class logger {
    public:
        enum class sink {
            stdout_sink,
            stderr_sink,
            file_sink,
            disabled,
        };

        static void set_sink(sink target, const std::string &file_path = std::string()) {
            std::lock_guard<std::mutex> guard(_mutex);
            if (target == sink::file_sink) {
                if (file_path.empty()) {
                    target = sink::stderr_sink;
                } else {
                    auto stream = std::make_unique<std::ofstream>(file_path, std::ios::out | std::ios::app);
                    if (!stream->is_open()) {
                        std::cerr << "vstd::logger: failed to open log file " << file_path
                                  << ", falling back to stderr" << std::endl;
                        target = sink::stderr_sink;
                    } else {
                        _file_stream = std::move(stream);
                        _current_sink = sink::file_sink;
                        return;
                    }
                }
            }
            _file_stream.reset();
            _current_sink = target;
        }

        template<typename ...Args>
        static void fatal(Args... args) {
            log("FATAL:", args...);
            std::terminate();
        }

        template<typename ...Args>
        static void error(Args... args) {
            log("ERROR:", args...);
        }

        template<typename ...Args>
        static void warning(Args... args) {
            log("WARNING:", args...);
        }

        template<typename ...Args>
        static void info(Args... args) {
            log("INFO:", args...);
        }

        template<typename ...Args>
        static void debug(Args... args) {
            log("DEBUG:", args...);
        }

    private:
        inline static sink _current_sink = sink::stdout_sink;
        inline static std::unique_ptr<std::ofstream> _file_stream;
        inline static std::mutex _mutex;

        template<typename T, typename U, typename ...Args>
        static void log(T t, U u, Args... args) {
            std::stringstream stream;
            stream << vstd::str(t) << " " << vstd::str(u);
            log(stream.str(), args...);
        }

        template<typename T>
        static void log(T t) {
            std::stringstream stream;
            stream << t;
            write_line(stream.str());
        }

        static void write_line(const std::string &line) {
            std::lock_guard<std::mutex> guard(_mutex);
            switch (_current_sink) {
            case sink::stdout_sink:
                std::cout << line << std::endl;
                break;
            case sink::stderr_sink:
                std::cerr << line << std::endl;
                break;
            case sink::file_sink:
                if (_file_stream && _file_stream->is_open()) {
                    (*_file_stream) << line << std::endl;
                } else {
                    std::cerr << line << std::endl;
                }
                break;
            case sink::disabled:
                break;
            }
        }
    };
}
