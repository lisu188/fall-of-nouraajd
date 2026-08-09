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

bool append_module_path(PyConfig &config, const std::filesystem::path &path) {
    wchar_t *decoded = Py_DecodeLocale(path.string().c_str(), nullptr);
    if (decoded == nullptr) {
        SDL_LogError(SDL_LOG_CATEGORY_APPLICATION, "Failed to decode Python module path: %s", path.string().c_str());
        return false;
    }
    const PyStatus status = PyWideStringList_Append(&config.module_search_paths, decoded);
    PyMem_RawFree(decoded);
    if (PyStatus_Exception(status)) {
        SDL_LogError(SDL_LOG_CATEGORY_APPLICATION, "Failed to append Python module path: %s", path.string().c_str());
        return false;
    }
    return true;
}

bool append_optional_module_path(PyConfig &config, const std::filesystem::path &path) {
    std::error_code errorCode;
    return !std::filesystem::is_directory(path, errorCode) || errorCode || append_module_path(config, path);
}

int run_python_game(const std::filesystem::path &runtimeRoot, const std::filesystem::path &pythonRoot,
                    const std::filesystem::path &stdlibRoot) {
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
    config.module_search_paths_set = 1;

    PyStatus status = PyConfig_SetBytesString(&config, &config.home, pythonRoot.string().c_str());
    if (!PyStatus_Exception(status) && !append_module_path(config, runtimeRoot)) {
        status = PyStatus_Error("failed to configure game runtime path");
    }
    if (!PyStatus_Exception(status) && !append_module_path(config, stdlibRoot)) {
        status = PyStatus_Error("failed to configure Python standard-library path");
    }
    if (!PyStatus_Exception(status) && !append_optional_module_path(config, stdlibRoot / "lib-dynload")) {
        status = PyStatus_Error("failed to configure Python extension-module path");
    }
    if (!PyStatus_Exception(status) && !append_optional_module_path(config, stdlibRoot / "site-packages")) {
        status = PyStatus_Error("failed to configure Python site-packages path");
    }

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
    PyObject *gameModule = PyImport_ImportModule("game");
    if (gameModule == nullptr) {
        PyErr_Print();
        SDL_LogError(SDL_LOG_CATEGORY_APPLICATION, "Failed to import game.py");
        result = 23;
    } else {
        PyObject *callResult = PyObject_CallMethod(gameModule, "new", nullptr);
        if (callResult == nullptr) {
            PyErr_Print();
            SDL_LogError(SDL_LOG_CATEGORY_APPLICATION, "game.new() failed");
            result = 24;
        }
        Py_XDECREF(callResult);
        Py_DECREF(gameModule);
    }

    if (Py_FinalizeEx() < 0 && result == 0) {
        result = 25;
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
    const auto stdlibRoot = find_python_stdlib(pythonRoot);
    if (!stdlibRoot) {
        SDL_LogError(SDL_LOG_CATEGORY_APPLICATION, "Expected exactly one extracted python3.* standard-library directory");
        return 13;
    }
    if (!CResourcesProvider::configurePlatformRoots(runtimeRoot.string(), writableRoot.string())) {
        return 14;
    }

    const int result = run_python_game(runtimeRoot, pythonRoot, *stdlibRoot);
    CResourcesProvider::clearPlatformRoots();
    return result;
}

#endif
