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
#if defined(__ANDROID__)

#include "core/CProvider.h"

#include <Python.h>
#include <SDL.h>
#include <SDL_system.h>

#include <cstdlib>
#include <filesystem>
#include <optional>
#include <string>

extern "C" PyObject *PyInit__game();

namespace {

std::optional<std::filesystem::path> find_python_stdlib(const std::filesystem::path &pythonRoot) {
    const auto libraryRoot = pythonRoot / "lib";
    std::error_code errorCode;
    if (!std::filesystem::is_directory(libraryRoot, errorCode) || errorCode) {
        return std::nullopt;
    }

    std::optional<std::filesystem::path> result;
    for (std::filesystem::directory_iterator it(libraryRoot, errorCode), end; !errorCode && it != end; it.increment(errorCode)) {
        if (!it->is_directory(errorCode) || errorCode) {
            continue;
        }
        const std::string name = it->path().filename().string();
        if (name.rfind("python3.", 0) != 0) {
            continue;
        }
        if (result) {
            return std::nullopt;
        }
        result = it->path();
    }
    return errorCode ? std::nullopt : result;
}

bool configure_python_temp_directory(const std::filesystem::path &writableRoot) {
    const char *existing = std::getenv("TMPDIR");
    if (existing != nullptr && *existing != '\0') {
        return true;
    }

    const auto tempRoot = writableRoot / "tmp";
    std::error_code errorCode;
    std::filesystem::create_directories(tempRoot, errorCode);
    if (errorCode) {
        SDL_LogError(SDL_LOG_CATEGORY_APPLICATION, "Failed to create Python temporary directory: %s",
                     tempRoot.string().c_str());
        return false;
    }
    if (::setenv("TMPDIR", tempRoot.string().c_str(), 0) != 0) {
        SDL_LogError(SDL_LOG_CATEGORY_APPLICATION, "Failed to configure TMPDIR for embedded Python");
        return false;
    }
    return true;
}

bool prepend_runtime_path(const std::filesystem::path &runtimeRoot) {
    PyObject *sysPath = PySys_GetObject("path");
    if (sysPath == nullptr || !PyList_Check(sysPath)) {
        return false;
    }

    PyObject *runtimePath = PyUnicode_DecodeFSDefault(runtimeRoot.string().c_str());
    if (runtimePath == nullptr) {
        return false;
    }
    const int result = PyList_Insert(sysPath, 0, runtimePath);
    Py_DECREF(runtimePath);
    return result == 0;
}

int run_python_game(const std::filesystem::path &runtimeRoot, const std::filesystem::path &pythonRoot) {
    if (PyImport_AppendInittab("_game", &PyInit__game) == -1) {
        SDL_LogError(SDL_LOG_CATEGORY_APPLICATION, "Failed to register built-in _game Python module");
        return 20;
    }

    PyConfig config;
    PyConfig_InitPythonConfig(&config);
    config.isolated = 1;
    config.use_environment = 0;
    config.parse_argv = 0;
    config.install_signal_handlers = 0;

    PyStatus status = PyConfig_SetBytesString(&config, &config.home, pythonRoot.string().c_str());
    if (PyStatus_Exception(status)) {
        SDL_LogError(SDL_LOG_CATEGORY_APPLICATION, "Failed to configure embedded Python: %s",
                     status.err_msg == nullptr ? "unknown error" : status.err_msg);
        PyConfig_Clear(&config);
        return 21;
    }

    status = Py_InitializeFromConfig(&config);
    PyConfig_Clear(&config);
    if (PyStatus_Exception(status)) {
        SDL_LogError(SDL_LOG_CATEGORY_APPLICATION, "Failed to initialize embedded Python: %s",
                     status.err_msg == nullptr ? "unknown error" : status.err_msg);
        return 22;
    }

    int result = 0;
    if (!prepend_runtime_path(runtimeRoot)) {
        PyErr_Print();
        SDL_LogError(SDL_LOG_CATEGORY_APPLICATION, "Failed to prepend the game runtime to sys.path");
        result = 23;
    } else {
        PyObject *gameModule = PyImport_ImportModule("game");
        if (gameModule == nullptr) {
            PyErr_Print();
            SDL_LogError(SDL_LOG_CATEGORY_APPLICATION, "Failed to import game.py");
            result = 24;
        } else {
            PyObject *callResult = PyObject_CallMethod(gameModule, "new", nullptr);
            if (callResult == nullptr) {
                PyErr_Print();
                SDL_LogError(SDL_LOG_CATEGORY_APPLICATION, "game.new() failed");
                result = 25;
            }
            Py_XDECREF(callResult);
            Py_DECREF(gameModule);
        }
    }

    if (Py_FinalizeEx() < 0 && result == 0) {
        result = 26;
    }
    return result;
}

} // namespace

int main(int, char **) {
    const char *internalStorage = SDL_AndroidGetInternalStoragePath();
    if (internalStorage == nullptr || *internalStorage == '\0') {
        SDL_LogError(SDL_LOG_CATEGORY_APPLICATION, "SDL did not provide Android internal storage path");
        return 10;
    }

    const std::filesystem::path filesRoot(internalStorage);
    const auto runtimeRoot = filesRoot / "runtime";
    const auto writableRoot = filesRoot / "user";
    const auto pythonRoot = filesRoot / "python";

    if (!std::filesystem::is_directory(runtimeRoot)) {
        SDL_LogError(SDL_LOG_CATEGORY_APPLICATION, "Extracted game runtime is missing: %s", runtimeRoot.string().c_str());
        return 11;
    }
    if (!std::filesystem::is_directory(pythonRoot)) {
        SDL_LogError(SDL_LOG_CATEGORY_APPLICATION, "Extracted Python runtime is missing: %s", pythonRoot.string().c_str());
        return 12;
    }
    if (!find_python_stdlib(pythonRoot)) {
        SDL_LogError(SDL_LOG_CATEGORY_APPLICATION, "Expected exactly one extracted python3.* standard-library directory");
        return 13;
    }
    if (!CResourcesProvider::configurePlatformRoots(runtimeRoot.string(), writableRoot.string())) {
        return 14;
    }
    if (!configure_python_temp_directory(writableRoot)) {
        CResourcesProvider::clearPlatformRoots();
        return 15;
    }

    const int result = run_python_game(runtimeRoot, pythonRoot);
    CResourcesProvider::clearPlatformRoots();
    return result;
}

#endif
