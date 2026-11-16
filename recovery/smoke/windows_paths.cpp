// Copyright (C) 2026 Andrzej Lis
// SPDX-License-Identifier: GPL-3.0-or-later
//
// The historical game was developed on Windows, whose file system matches names
// case-insensitively (for example the code opens config/items/Robe.json while the
// file is robe.json). Preloaded only into the startup-verification process, this shim
// gives file lookups the same semantics: when a path does not exist exactly, each
// missing component is matched case-insensitively against its directory before the
// real call is made. Existing paths and failed lookups behave exactly as before.
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <dirent.h>
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include <unistd.h>

#include <string>

namespace {

template <typename Function> Function real(const char *name) {
    return reinterpret_cast<Function>(dlsym(RTLD_NEXT, name));
}

bool exists(const std::string &path) {
    static auto realAccess = real<int (*)(const char *, int)>("access");
    return realAccess(path.c_str(), F_OK) == 0;
}

// Returns the case-insensitively resolved path, or the original when nothing matches.
std::string resolve(const char *path) {
    if (!path || !*path || exists(path)) {
        return path ? path : "";
    }
    const int savedErrno = errno;
    std::string input(path), resolved = input[0] == '/' ? "/" : "";
    size_t position = 0;
    while (position <= input.size()) {
        size_t next = input.find('/', position);
        if (next == std::string::npos) {
            next = input.size();
        }
        std::string part = input.substr(position, next - position);
        position = next + 1;
        if (part.empty() || part == ".") {
            continue;
        }
        std::string directory = resolved.empty() ? "." : resolved;
        std::string candidate = resolved + (resolved.empty() || resolved.back() == '/' ? "" : "/") + part;
        if (part != ".." && !exists(candidate)) {
            DIR *handle = opendir(directory.c_str());
            bool found = false;
            if (handle) {
                while (dirent *entry = readdir(handle)) {
                    if (strcasecmp(entry->d_name, part.c_str()) == 0) {
                        candidate = resolved + (resolved.empty() || resolved.back() == '/' ? "" : "/") + entry->d_name;
                        found = true;
                        break;
                    }
                }
                closedir(handle);
            }
            if (!found) {
                errno = savedErrno;
                return input;
            }
        }
        resolved = candidate;
    }
    errno = savedErrno;
    return resolved.empty() ? input : resolved;
}

} // namespace

extern "C" {

int open(const char *path, int flags, ...) {
    static auto realOpen = real<int (*)(const char *, int, ...)>("open");
    mode_t mode = 0;
    if (flags & O_CREAT) {
        va_list arguments;
        va_start(arguments, flags);
        mode = static_cast<mode_t>(va_arg(arguments, int));
        va_end(arguments);
        return realOpen(path, flags, mode);
    }
    return realOpen(resolve(path).c_str(), flags);
}

int open64(const char *path, int flags, ...) {
    static auto realOpen = real<int (*)(const char *, int, ...)>("open64");
    mode_t mode = 0;
    if (flags & O_CREAT) {
        va_list arguments;
        va_start(arguments, flags);
        mode = static_cast<mode_t>(va_arg(arguments, int));
        va_end(arguments);
        return realOpen(path, flags, mode);
    }
    return realOpen(resolve(path).c_str(), flags);
}

FILE *fopen(const char *path, const char *mode) {
    static auto realFopen = real<FILE *(*)(const char *, const char *)>("fopen");
    return realFopen(mode && mode[0] == 'r' ? resolve(path).c_str() : path, mode);
}

FILE *fopen64(const char *path, const char *mode) {
    static auto realFopen = real<FILE *(*)(const char *, const char *)>("fopen64");
    return realFopen(mode && mode[0] == 'r' ? resolve(path).c_str() : path, mode);
}

int access(const char *path, int mode) {
    static auto realAccess = real<int (*)(const char *, int)>("access");
    return realAccess(resolve(path).c_str(), mode);
}

int __xstat(int version, const char *path, struct stat *buffer) {
    static auto realStat = real<int (*)(int, const char *, struct stat *)>("__xstat");
    return realStat(version, resolve(path).c_str(), buffer);
}

int __xstat64(int version, const char *path, struct stat64 *buffer) {
    static auto realStat = real<int (*)(int, const char *, struct stat64 *)>("__xstat64");
    return realStat(version, resolve(path).c_str(), buffer);
}

int __lxstat(int version, const char *path, struct stat *buffer) {
    static auto realStat = real<int (*)(int, const char *, struct stat *)>("__lxstat");
    return realStat(version, resolve(path).c_str(), buffer);
}

int __lxstat64(int version, const char *path, struct stat64 *buffer) {
    static auto realStat = real<int (*)(int, const char *, struct stat64 *)>("__lxstat64");
    return realStat(version, resolve(path).c_str(), buffer);
}

} // extern "C"
