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

#include <optional>

namespace {

struct PlatformResourceState {
    std::optional<std::list<std::string>> defaultSearchPath;
};

PlatformResourceState &platformResourceState() {
    static PlatformResourceState state;
    return state;
}

std::optional<std::string> canonicalDirectory(const std::string &path, bool createIfMissing) {
    if (path.empty()) {
        return std::nullopt;
    }

    std::error_code errorCode;
    const std::filesystem::path requested(path);
    if (createIfMissing) {
        std::filesystem::create_directories(requested, errorCode);
        if (errorCode) {
            return std::nullopt;
        }
    }

    if (!std::filesystem::is_directory(requested, errorCode) || errorCode) {
        return std::nullopt;
    }

    auto canonical = std::filesystem::weakly_canonical(requested, errorCode);
    if (errorCode) {
        return std::nullopt;
    }
    return canonical.string();
}

} // namespace

bool CResourcesProvider::configurePlatformRoots(const std::string &packagedRoot, const std::string &writableRoot) {
    const auto packaged = canonicalDirectory(packagedRoot, false);
    if (!packaged) {
        vstd::logger::warning("Failed to configure packaged resource root:", packagedRoot,
                              "reason:", "root is not an existing directory");
        return false;
    }

    const auto writable = canonicalDirectory(writableRoot, true);
    if (!writable) {
        vstd::logger::warning("Failed to configure writable resource root:", writableRoot,
                              "reason:", "root could not be created or opened as a directory");
        return false;
    }

    auto &state = platformResourceState();
    if (!state.defaultSearchPath) {
        state.defaultSearchPath = searchPath;
    }

    searchPath = *state.defaultSearchPath;
    searchPath.remove(*packaged);
    searchPath.remove(*writable);
    searchPath.push_front(*packaged);
    searchPath.push_front(*writable);

    vstd::logger::info("Configured platform resource roots; writable:", *writable, "packaged:", *packaged);
    return true;
}

void CResourcesProvider::clearPlatformRoots() {
    auto &state = platformResourceState();
    if (!state.defaultSearchPath) {
        return;
    }
    searchPath = *state.defaultSearchPath;
}
