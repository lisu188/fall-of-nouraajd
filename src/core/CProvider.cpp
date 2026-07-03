/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025-2026  Andrzej Lis

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
#include "core/CGame.h"
#include "core/CJsonUtil.h"
#include "core/CSaveFormat.h"
#include "gui/CAnimation.h"

#include <algorithm>
#include <chrono>
#include <cctype>
#include <utility>

#ifdef _WIN32
#include <windows.h>
#else
#include <dlfcn.h>
#include <fcntl.h>
#include <unistd.h>
#endif

namespace {

std::optional<std::filesystem::path> normalizeSafeRelativeResourcePath(const std::string &path) {
    const std::filesystem::path resourcePath(path);
    if (path.empty() || resourcePath.is_absolute() || resourcePath.has_root_name()) {
        return std::nullopt;
    }

    const auto normalized = resourcePath.lexically_normal().generic_string();
    if (normalized.empty() || normalized == "." || normalized == ".." || normalized.rfind("../", 0) == 0 ||
        normalized.find("/../") != std::string::npos) {
        return std::nullopt;
    }
    return std::filesystem::path(normalized);
}

bool isSafeRelativeResourcePath(const std::string &path) { return normalizeSafeRelativeResourcePath(path).has_value(); }

bool isConfigResourcePath(const std::string &path) {
    const std::filesystem::path resourcePath(path);
    return isSafeRelativeResourcePath(path) &&
           (!resourcePath.has_parent_path() || resourcePath.parent_path() == std::filesystem::path("config"));
}

std::filesystem::path uniqueTempPathFor(const std::filesystem::path &path) {
    const auto nonce = std::chrono::steady_clock::now().time_since_epoch().count();
    const auto prefix = "." + path.filename().string() + "." + std::to_string(nonce);
    auto candidate = path.parent_path() / (prefix + ".tmp");
    for (int attempt = 1; std::filesystem::exists(candidate) && attempt < 100; ++attempt) {
        candidate = path.parent_path() / (prefix + "." + std::to_string(attempt) + ".tmp");
    }
    return candidate;
}

void logSaveFailure(const std::filesystem::path &path, const std::string &stage, const std::string &reason) {
    vstd::logger::warning("Failed to save resource:", path.string(), "stage:", stage, "reason:", reason);
}

bool removePathIfExists(const std::filesystem::path &path, const std::string &stage) {
    std::error_code errorCode;
    if (!std::filesystem::exists(path, errorCode)) {
        return true;
    }
    if (errorCode) {
        logSaveFailure(path, stage, errorCode.message());
        return false;
    }
    std::filesystem::remove(path, errorCode);
    if (errorCode) {
        logSaveFailure(path, stage, errorCode.message());
        return false;
    }
    return true;
}

bool writeTextFile(const std::filesystem::path &path, const std::string &data) {
    std::ofstream stream(path, std::ios::binary | std::ios::trunc);
    if (!stream) {
        logSaveFailure(path, "write-temp-open", "could not open temp file");
        return false;
    }
    stream.write(data.data(), static_cast<std::streamsize>(data.size()));
    stream.flush();
    if (!stream) {
        logSaveFailure(path, "write-temp-flush", "temp file write failed");
        return false;
    }
    stream.close();
    if (!stream) {
        logSaveFailure(path, "write-temp-close", "temp file close failed");
        return false;
    }
    return true;
}

void flushFileBestEffort(const std::filesystem::path &path) {
#ifdef _WIN32
    HANDLE handle = CreateFileW(path.wstring().c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr,
                                OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (handle == INVALID_HANDLE_VALUE) {
        return;
    }
    FlushFileBuffers(handle);
    CloseHandle(handle);
#else
    const int fd = ::open(path.c_str(), O_RDONLY);
    if (fd < 0) {
        return;
    }
    (void)::fsync(fd);
    (void)::close(fd);
#endif
}

void flushDirectoryBestEffort(const std::filesystem::path &path) {
#ifdef _WIN32
    HANDLE handle = CreateFileW(path.wstring().c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr,
                                OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, nullptr);
    if (handle == INVALID_HANDLE_VALUE) {
        return;
    }
    FlushFileBuffers(handle);
    CloseHandle(handle);
#else
    const int fd = ::open(path.c_str(), O_RDONLY | O_DIRECTORY);
    if (fd < 0) {
        return;
    }
    (void)::fsync(fd);
    (void)::close(fd);
#endif
}

bool restoreBackup(const std::filesystem::path &backupPath, const std::filesystem::path &path) {
    std::error_code errorCode;
    if (std::filesystem::exists(path, errorCode) && !removePathIfExists(path, "restore-remove-partial-primary")) {
        return false;
    }
    std::filesystem::rename(backupPath, path, errorCode);
    if (errorCode) {
        logSaveFailure(path, "restore-backup", errorCode.message());
        return false;
    }
    flushDirectoryBestEffort(path.parent_path());
    return true;
}

bool saveAtomicallyResolved(const std::filesystem::path &path, const std::string &data) {
    if (path.empty()) {
        logSaveFailure(path, "validate-path", "unsafe relative path");
        return false;
    }

    const auto normalizedPath = path.lexically_normal();
    const auto dir = normalizedPath.parent_path();
    std::error_code errorCode;
    if (!dir.empty()) {
        std::filesystem::create_directories(dir, errorCode);
        if (errorCode) {
            logSaveFailure(normalizedPath, "create-directory", errorCode.message());
            return false;
        }
    }

    const auto tempPath = uniqueTempPathFor(normalizedPath);
    const auto backupPath = std::filesystem::path(normalizedPath.string() + CSaveFormat::BACKUP_SUFFIX);
    bool primaryMovedToBackup = false;

    if (!writeTextFile(tempPath, data)) {
        removePathIfExists(tempPath, "cleanup-temp-after-write-failure");
        return false;
    }
    flushFileBestEffort(tempPath);

    if (std::filesystem::exists(normalizedPath, errorCode)) {
        if (!removePathIfExists(backupPath, "remove-old-backup")) {
            removePathIfExists(tempPath, "cleanup-temp-after-backup-failure");
            return false;
        }
        std::filesystem::rename(normalizedPath, backupPath, errorCode);
        if (errorCode) {
            logSaveFailure(normalizedPath, "rotate-primary-to-backup", errorCode.message());
            removePathIfExists(tempPath, "cleanup-temp-after-rotate-failure");
            return false;
        }
        flushDirectoryBestEffort(dir);
        primaryMovedToBackup = true;
    } else if (errorCode) {
        logSaveFailure(normalizedPath, "check-primary", errorCode.message());
        removePathIfExists(tempPath, "cleanup-temp-after-primary-check-failure");
        return false;
    }

    std::filesystem::rename(tempPath, normalizedPath, errorCode);
    if (errorCode) {
        logSaveFailure(normalizedPath, "promote-temp", errorCode.message());
        if (primaryMovedToBackup) {
            restoreBackup(backupPath, normalizedPath);
        }
        removePathIfExists(tempPath, "cleanup-temp-after-promote-failure");
        return false;
    }

    flushDirectoryBestEffort(dir);
    return true;
}

std::filesystem::path providerModulePathAnchor() { return std::filesystem::path(); }

std::filesystem::path getModuleResourceRoot() {
#ifdef _WIN32
    HMODULE moduleHandle = nullptr;
    if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           reinterpret_cast<LPCSTR>(&providerModulePathAnchor), &moduleHandle) == 0) {
        return {};
    }

    std::string buffer(MAX_PATH, '\0');
    DWORD length = 0;
    while (true) {
        length = GetModuleFileNameA(moduleHandle, buffer.data(), static_cast<DWORD>(buffer.size()));
        if (length == 0) {
            return {};
        }
        if (length < buffer.size() - 1) {
            buffer.resize(length);
            break;
        }
        buffer.resize(buffer.size() * 2, '\0');
    }
    return std::filesystem::path(buffer).parent_path();
#else
    Dl_info info{};
    if (dladdr(reinterpret_cast<void *>(&providerModulePathAnchor), &info) == 0 || info.dli_fname == nullptr) {
        return {};
    }
    return std::filesystem::path(info.dli_fname).parent_path();
#endif
}

std::list<std::string> buildResourceSearchPath() {
    std::list<std::string> paths;
    auto moduleRoot = getModuleResourceRoot();
    if (!moduleRoot.empty()) {
        std::error_code errorCode;
        auto canonicalModuleRoot = std::filesystem::weakly_canonical(moduleRoot, errorCode);
        if (!errorCode) {
            paths.push_back(canonicalModuleRoot.string());
        }
    }
    return paths;
}

bool isWithinResourceRoot(const std::filesystem::path &candidate, const std::filesystem::path &root) {
    auto candidateIt = candidate.begin();
    auto rootIt = root.begin();
    for (; rootIt != root.end(); ++rootIt, ++candidateIt) {
        if (candidateIt == candidate.end() || *candidateIt != *rootIt) {
            return false;
        }
    }
    return true;
}

std::filesystem::path resolveWritableResourcePath(const std::list<std::string> &roots, const std::string &path) {
    const auto requestedPath = normalizeSafeRelativeResourcePath(path);
    if (!requestedPath) {
        return {};
    }

    for (const auto &root : roots) {
        if (root.empty()) {
            continue;
        }

        std::error_code errorCode;
        auto resourceRoot = std::filesystem::weakly_canonical(root, errorCode);
        if (errorCode) {
            continue;
        }

        auto candidate = (resourceRoot / *requestedPath).lexically_normal();
        if (isWithinResourceRoot(candidate, resourceRoot)) {
            return candidate;
        }
    }
    return {};
}

} // namespace

const std::string CResType::CONFIG = "CONFIG";
const std::string CResType::MAP = "MAP";
const std::string CResType::PLUGIN = "PLUGIN";
const std::string CResType::SAVE = "SAVE";

CConfigurationProvider::CConfigurationProvider(std::shared_ptr<CResourcesProvider> resourcesProvider)
    : resourcesProvider(std::move(resourcesProvider)) {
    if (!this->resourcesProvider) {
        this->resourcesProvider = CResourcesProvider::getInstance();
    }
}

// Compatibility-only: serves callers without a game context through a cache that lives for the
// whole process. Game-attached code must use CGame::getConfigurationProvider() instead.
std::shared_ptr<json> CConfigurationProvider::getConfig(const std::string &path) {
    static CConfigurationProvider instance;
    return instance.getConfiguration(path);
}

CConfigurationProvider::~CConfigurationProvider() = default;

std::shared_ptr<json> CConfigurationProvider::getConfiguration(const std::string &path) {
    auto config = configurations.find(path);
    if (config != configurations.end()) {
        return config->second;
    }
    loadConfig(path);
    config = configurations.find(path);
    return config != configurations.end() ? config->second : nullptr;
}

void CConfigurationProvider::loadConfig(const std::string &path) {
    if (isConfigResourcePath(path)) {
        auto config = CConfigResourceLoader().load(path);
        configurations.emplace(path, CJsonUtil::from_string(resourcesProvider->load(config->getFilePath()), path));
        return;
    }

    configurations.emplace(path, resourcesProvider->loadJson(path));
}

std::list<std::string> CResourcesProvider::searchPath = buildResourceSearchPath();

// Compatibility-only: process-wide provider shared by every caller without a game context,
// including Python scripts and plugins. Game-attached code must use CGame::getResourcesProvider().
std::shared_ptr<CResourcesProvider> CResourcesProvider::getInstance() {
    static std::shared_ptr<CResourcesProvider> instance = std::make_shared<CResourcesProvider>();
    return instance;
}

std::expected<std::string, CResourcesProvider::LoadFailure>
CResourcesProvider::loadExpected(std::string path, std::source_location location) {
    const std::string requestedPath = path;
    auto resolvedPath = getPath(std::move(path));
    if (resolvedPath.empty()) {
        return std::unexpected(LoadFailure{requestedPath, resolvedPath, "resource path was not found", location});
    }

    std::ifstream stream(resolvedPath);
    if (!stream) {
        return std::unexpected(LoadFailure{requestedPath, resolvedPath, "resource file could not be opened", location});
    }

    return std::string(std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>());
}

void CResourcesProvider::logLoadFailure(const LoadFailure &failure) {
    vstd::logger::warning("Failed to load resource:", failure.requestedPath, "resolved:", failure.resolvedPath,
                          "reason:", failure.message);
}

std::string CResourcesProvider::load(std::string path) {
    auto result = loadExpected(std::move(path));
    if (!result) {
        logLoadFailure(result.error());
        return {};
    }
    return std::move(*result);
}

std::shared_ptr<json> CResourcesProvider::loadJson(std::string path) {
    auto source = path;
    auto text = loadExpected(std::move(path));
    if (!text) {
        logLoadFailure(text.error());
        return nullptr;
    }
    auto parsed = CJsonUtil::parse_expected(std::move(*text), source);
    if (!parsed) {
        CJsonUtil::log_parse_error(parsed.error());
        return nullptr;
    }
    return *parsed;
}

std::string CResourcesProvider::getPath(std::string path) {
    // Resolution precedence: the process-wide base search path is always consulted first, so global
    // assets keep their meaning; only if nothing matches there does the active map scope (if any)
    // get a chance to resolve a map-local asset of the same relative name. The safe-relative-path
    // guard below rejects absolute and traversal paths before any root — base or scoped — is tried.
    if (!isSafeRelativeResourcePath(path)) {
        vstd::logger::warning("Rejected unsafe resource path:", path);
        return {};
    }

    const auto requestedPath = std::filesystem::path(path).lexically_normal();
    for (const auto &root : searchPath) {
        if (root.empty()) {
            continue;
        }

        std::error_code errorCode;
        auto resourceRoot = std::filesystem::weakly_canonical(root, errorCode);
        if (errorCode) {
            continue;
        }

        const auto candidatePath = resourceRoot / requestedPath;
        if (!std::filesystem::exists(candidatePath, errorCode) || errorCode) {
            continue;
        }

        auto candidate = std::filesystem::weakly_canonical(candidatePath, errorCode);
        if (errorCode) {
            continue;
        }
        if (isWithinResourceRoot(candidate, resourceRoot) && std::filesystem::exists(candidate)) {
            return candidate.string();
        }
    }

    if (!activeScope.empty()) {
        const auto scope = scopedRoots.find(activeScope);
        if (scope != scopedRoots.end()) {
            std::error_code errorCode;
            const std::filesystem::path resourceRoot(scope->second.canonicalRoot);
            const auto candidatePath = resourceRoot / requestedPath;
            auto candidate = std::filesystem::weakly_canonical(candidatePath, errorCode);
            if (!errorCode && isWithinResourceRoot(candidate, resourceRoot) && std::filesystem::exists(candidate)) {
                return candidate.string();
            }
        }
    }
    return {};
}

void CResourcesProvider::addScopedRoot(const std::string &scope, const std::string &root) {
    auto existing = scopedRoots.find(scope);
    if (existing != scopedRoots.end()) {
        ++existing->second.refCount;
        return;
    }

    std::error_code errorCode;
    const auto canonicalRoot = std::filesystem::weakly_canonical(root, errorCode);
    if (errorCode || root.empty() || !std::filesystem::is_directory(canonicalRoot, errorCode) || errorCode) {
        vstd::logger::warning("Ignoring scoped resource root:", scope, "root:", root,
                              "reason:", "root is not an existing directory");
        return;
    }

    scopedRoots.emplace(scope, ScopedRoot{canonicalRoot.string(), 1});
}

void CResourcesProvider::releaseScopedRoot(const std::string &scope) {
    auto existing = scopedRoots.find(scope);
    if (existing == scopedRoots.end()) {
        return;
    }
    if (--existing->second.refCount <= 0) {
        scopedRoots.erase(existing);
        if (activeScope == scope) {
            activeScope.clear();
        }
    }
}

void CResourcesProvider::setActiveScope(const std::string &scope) { activeScope = scope; }

std::string CResourcesProvider::getActiveScope() const { return activeScope; }

std::vector<std::string> CResourcesProvider::getScopedRoots() const {
    std::vector<std::string> roots;
    roots.reserve(scopedRoots.size());
    for (const auto &[scope, scopedRoot] : scopedRoots) {
        roots.push_back(scopedRoot.canonicalRoot);
    }
    std::ranges::sort(roots);
    return roots;
}

std::vector<std::string> CResourcesProvider::getFiles(const std::string &type) {
    std::vector<std::string> retValue;
    std::set<std::string> saveSlots;
    std::string folderName;
    std::string suffix;

    if (type == CResType::CONFIG) {
        folderName = "config";
        suffix = "json";
    } else if (type == CResType::PLUGIN) {
        folderName = "plugins";
        suffix = "py";
    } else if (type == CResType::MAP) {
        folderName = "maps";
    } else if (type == CResType::SAVE) {
        folderName = "save";
        suffix = "json";
    } else {
        vstd::logger::fatal("Unknown resource type:", type);
    }

    const auto resolvedFolderName = getPath(folderName);
    std::error_code errorCode;
    const bool directoryExists =
        !resolvedFolderName.empty() && std::filesystem::is_directory(resolvedFolderName, errorCode);
    if (!directoryExists) {
        if (type == CResType::SAVE) {
            vstd::logger::debug("Optional resource directory is missing:", folderName);
        } else {
            vstd::logger::warning("Resource directory is missing:", folderName);
        }
        return retValue;
    }

    const auto folderPath = std::filesystem::path(resolvedFolderName);
    const auto resourceRoot = folderPath.parent_path();
    std::filesystem::directory_iterator dir(folderPath), end;
    while (dir != end) {
        if (type == CResType::SAVE) {
            if (dir->is_regular_file(errorCode)) {
                const auto filename = dir->path().filename();
                if (auto slotName = CSaveFormat::primarySlotFromFilename(filename)) {
                    saveSlots.insert(*slotName);
                } else if (auto backupSlotName = CSaveFormat::backupSlotFromFilename(filename)) {
                    const auto primaryPath = folderPath / (backupSlotName.value() + ".json");
                    if (!std::filesystem::exists(primaryPath, errorCode)) {
                        saveSlots.insert(*backupSlotName);
                    }
                }
            }
        } else if (type == CResType::MAP) {
            auto pt = dir->path().filename().stem().string();
            retValue.push_back(pt);
        } else {
            auto pt = std::filesystem::relative(dir->path(), resourceRoot).generic_string();
            if (vstd::ends_with(pt, vstd::join({".", suffix}, ""))) {
                retValue.push_back(pt);
            }
        }
        dir++;
    }
    if (type == CResType::SAVE) {
        retValue.assign(saveSlots.begin(), saveSlots.end());
    }
    std::ranges::sort(retValue);
    return retValue;
}

bool CResourcesProvider::save(std::string file, const std::string &data) {
    const auto requestedFile = file;
    const auto resolvedPath = resolveWritableResourcePath(searchPath, requestedFile);
    vstd::logger::info("Saving resource:", requestedFile, "resolved:", resolvedPath.string());
    if (resolvedPath.empty()) {
        logSaveFailure(requestedFile, "resolve-path", "resource path was not found");
        return false;
    }
    if (!saveAtomicallyResolved(resolvedPath, data)) {
        vstd::logger::warning("Save failed; previous resource copy was preserved where possible", requestedFile,
                              "resolved:", resolvedPath.string());
        return false;
    }
    return true;
}

bool CResourcesProvider::save(std::string file, std::shared_ptr<json> data) {
    return save(std::move(file), CJsonUtil::to_string(std::move(data)));
}

std::shared_ptr<CAnimation> CAnimationProvider::getAnimation(const std::shared_ptr<CGame> &game,
                                                             const std::shared_ptr<CGameObject> &object, bool custom) {
    if (!game || !object) {
        return nullptr;
    }
    auto animation = game->createObject<CAnimation>("CAnimation");
    auto animationPath = object->getAnimation();
    const auto resolvedAnimationPath = game->getResourcesProvider()->getPath(animationPath);
    if (!resolvedAnimationPath.empty() && std::filesystem::is_directory(resolvedAnimationPath)) {
        animation = game->createObject<CDynamicAnimation>("CDynamicAnimation");
    } else if (std::filesystem::is_regular_file(game->getResourcesProvider()->getPath(animationPath + ".png"))) {
        animation = custom ? game->createObject<CAnimation>("CCustomAnimation")
                           : game->createObject<CStaticAnimation>("CStaticAnimation");
    } else {
        // TODO: if the path wasnt empty load text instead, requires changes in text
        // manager
        vstd::logger::warning("Loading empty animation");
    }
    if (!animation) {
        vstd::logger::warning("Skipping animation with unregistered animation type:", object->getAnimation());
        return nullptr;
    }
    animation->setObject(object);
    return animation;
}

std::shared_ptr<CAnimation> CAnimationProvider::getAnimation(const std::shared_ptr<CGame> &game, std::string path,
                                                             bool custom) {
    std::shared_ptr<CGameObject> object = game->createObject<CGameObject>();
    if (!object) {
        vstd::logger::warning("Skipping animation path with unregistered CGameObject type:", path);
        return nullptr;
    }
    object->setAnimation(std::move(path));
    auto animation = getAnimation(game, object, custom);
    if (animation) {
        animation->setOwnedObject(object);
    }
    return animation;
}

const std::string &CResource::getPath() const { return path; }

void CResource::setPath(const std::string &path) { CResource::path = path; }

const std::string &CResource::getPathPrefix() const { return pathPrefix; }

void CResource::setPathPrefix(const std::string &pathPrefix) { CResource::pathPrefix = pathPrefix; }

const std::string &CResource::getPathSuffix() const { return pathSuffix; }

void CResource::setPathSuffix(const std::string &pathSuffix) { CResource::pathSuffix = pathSuffix; }

std::string CResource::getFilePath() const {
    return (std::filesystem::path(getPathPrefix()) /
            std::filesystem::path(getPath()).replace_extension(getPathSuffix()))
        .string();
}

std::string CTextResource::getText() {
    const auto filePath = getFilePath();
    // Resolve through the owning game's per-session resources provider; fall back to the process
    // singleton only for resources that were never attached to a game (compatibility path).
    auto game = getGame();
    auto resourcesProvider = game ? game->getResourcesProvider() : CResourcesProvider::getInstance();
    auto resolvedPath = resourcesProvider->getPath(filePath);
    if (resolvedPath.empty()) {
        return {};
    }

    std::ifstream t(resolvedPath);
    return std::string(std::istreambuf_iterator<char>(t), std::istreambuf_iterator<char>());
}
