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
#include "core/CRuntimeBridge.h"

#include <exception>
#include <utility>

std::shared_ptr<vstd::event_loop<>> CRuntimeBridge::event_loop_instance() { return vstd::event_loop<>::instance(); }

void CRuntimeBridge::log_info(std::string message) { vstd::logger::info(std::move(message)); }

void CRuntimeBridge::set_logger_sink(vstd::logger::sink target, const std::string &path) {
    vstd::logger::set_sink(target, path);
}

void CPythonDiagnostics::logCurrentException(std::source_location location) noexcept {
    try {
        const auto error = std::current_exception();
        if (!error) {
            if (Py_IsInitialized() && PyGILState_Check() && PyErr_Occurred()) {
                PyErr_Print();
            }
            return;
        }
        try {
            std::rethrow_exception(error);
        } catch (const pybind11::error_already_set &exception) {
            if (!Py_IsInitialized()) {
                return;
            }
#if PY_VERSION_HEX >= 0x030D0000
            if (Py_IsFinalizing()) {
#else
            if (_Py_IsFinalizing()) {
#endif
                return;
            }
            vstd::logger::error("Python callback failed:", location.function_name(), "at", location.file_name(),
                                location.line(), exception.what());
        } catch (const std::exception &exception) {
            vstd::logger::error("Callback failed:", location.function_name(), "at", location.file_name(),
                                location.line(), exception.what());
        } catch (...) {
            vstd::logger::error("Callback failed:", location.function_name(), "at", location.file_name(),
                                location.line(), "unknown exception");
        }
    } catch (...) {
        // Diagnostics must preserve the callback's existing recovery behavior.
    }
}
