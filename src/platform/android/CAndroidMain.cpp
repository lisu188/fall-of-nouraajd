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
#include "core/CProvider.h"

#include <Python.h>
#include <SDL.h>
#include <SDL_system.h>

#include <filesystem>
#include <string>

extern "C" PyObject *PyInit__game();

namespace {

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
    config.module_search_paths_set = 1;

    PyStatus status = PyConfig_SetBytesString(&config, &config.home, pythonRoot.string().c_str());
    if (!PyStatus_Exception(status) && !append_module_path(config, runtimeRoot)) {
        status = PyStatus_Error("failed to configure game runtime path");
    }
    if (!PyStatus_Exception(status) && !append_module_path(config, pythonRoot)) {
        status = PyStatus_Error("failed to configure Python standard-library path");
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
    if (!CResourcesProvider::configurePlatformRoots(runtimeRoot.string(), writableRoot.string())) {
        return 13;
    }

    const int result = run_python_game(runtimeRoot, pythonRoot);
    CResourcesProvider::clearPlatformRoots();
    return result;
}
