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
#pragma once

#if defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

#include <atomic>
#include <cstdint>
#include <cstdio>

namespace native_test_diagnostics {
inline LONG CALLBACK logWindowsCrash(EXCEPTION_POINTERS *exception) noexcept {
    if (!exception || !exception->ExceptionRecord || !exception->ContextRecord)
        return EXCEPTION_CONTINUE_SEARCH;
    const auto code = exception->ExceptionRecord->ExceptionCode;
    if (code < EXCEPTION_FLT_DENORMAL_OPERAND || code > EXCEPTION_INT_OVERFLOW)
        return EXCEPTION_CONTINUE_SEARCH;
    static std::atomic_flag logging = ATOMIC_FLAG_INIT;
    if (logging.test_and_set(std::memory_order_acquire))
        return EXCEPTION_CONTINUE_SEARCH;
    const auto address = exception->ExceptionRecord->ExceptionAddress;
    HMODULE module = nullptr;
    char modulePath[MAX_PATH] = "<unknown>";
    if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           reinterpret_cast<LPCSTR>(address), &module))
        GetModuleFileNameA(module, modulePath, MAX_PATH);
    const auto offset =
        module ? reinterpret_cast<std::uintptr_t>(address) - reinterpret_cast<std::uintptr_t>(module) : 0;
    std::fprintf(stderr, "[native-crash] code=0x%08lx module=%s offset=0x%llx\n", code, modulePath,
                 static_cast<unsigned long long>(offset));
#if defined(_M_X64) || defined(__x86_64__)
    const auto &registers = *exception->ContextRecord;
    std::fprintf(stderr, "[native-crash] rip=0x%llx rax=0x%llx rdx=0x%llx rcx=0x%llx rbx=0x%llx r8=0x%llx r9=0x%llx\n",
                 registers.Rip, registers.Rax, registers.Rdx, registers.Rcx, registers.Rbx, registers.R8, registers.R9);
#endif
    unsigned char instruction[16]{};
    SIZE_T bytes = 0;
    if (ReadProcessMemory(GetCurrentProcess(), address, instruction, sizeof(instruction), &bytes)) {
        std::fputs("[native-crash] instruction=", stderr);
        for (SIZE_T index = 0; index < bytes; ++index)
            std::fprintf(stderr, "%02x", instruction[index]);
        std::fputc('\n', stderr);
    }
    std::fflush(stderr);
    logging.clear(std::memory_order_release);
    return EXCEPTION_CONTINUE_SEARCH;
}

inline void installWindowsCrashDiagnostics() {
    // Keep this handler installed through static destruction, where shutdown failures may occur.
    static const auto handler = AddVectoredExceptionHandler(1, logWindowsCrash);
    (void)handler;
}
} // namespace native_test_diagnostics
#else
namespace native_test_diagnostics {
inline void installWindowsCrashDiagnostics() {}
} // namespace native_test_diagnostics
#endif
