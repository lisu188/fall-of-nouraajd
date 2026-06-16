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
#include "gui/CAnimation.h"

#ifdef _WIN32
#include <windows.h>
#else
#include <dlfcn.h>
#endif

namespace {

bool isConfigResourcePath(const std::string &path) {
    const std::filesystem::path resourcePath(path);
    return !resourcePath.has_parent_path() || resourcePath.parent_path() == std::filesystem::path("config");
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
        paths.push_back(std::filesystem::weakly_canonical(moduleRoot).string());
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

} // namespace

const std::string CResType::CONFIG = "CONFIG";
const std::string CResType::MAP = "MAP";
const std::string CResType::PLUGIN = "PLUGIN";
const std::string CResType::SAVE = "SAVE";

std::shared_ptr<json> CConfigurationProvider::getConfig(const std::string &path) {
    static CConfigurationProvider instance;
    return instance.getConfiguration(path);
}

CConfigurationProvider::~CConfigurationProvider() { clear(); }

std::shared_ptr<json> CConfigurationProvider::getConfiguration(const std::string &path) {
    if (this->find(path) != this->end()) {
        return this->at(path);
    }
    loadConfig(path);
    return getConfiguration(path);
}

void CConfigurationProvider::loadConfig(const std::string &path) {
    if (isConfigResourcePath(path)) {
        auto config = std::static_pointer_cast<CTextResource>(CConfigResourceLoader().load(path));
        this->insert(std::make_pair(path, CJsonUtil::from_string(config->getText(), path)));
        return;
    }

    this->insert(std::make_pair(path, CResourcesProvider::getInstance()->loadJson(path)));
}

std::list<std::string> CResourcesProvider::searchPath = buildResourceSearchPath();

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
    const std::filesystem::path requestedPath(std::move(path));
    if (requestedPath.is_absolute()) {
        return {};
    }

    for (const auto &root : searchPath) {
        if (root.empty()) {
            continue;
        }

        auto resourceRoot = std::filesystem::weakly_canonical(root);
        auto candidate = std::filesystem::weakly_canonical(resourceRoot / requestedPath);
        if (isWithinResourceRoot(candidate, resourceRoot) && std::filesystem::exists(candidate)) {
            return candidate.string();
        }
    }
    return {};
}

std::vector<std::string> CResourcesProvider::getFiles(const std::string &type) {
    std::vector<std::string> retValue;
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
        if (type == CResType::MAP || type == CResType::SAVE) {
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
    return retValue;
}

void CResourcesProvider::save(std::string file, const std::string &data) {
    vstd::logger::info("Saving map: " + file);
    std::filesystem::path path(file);
    std::filesystem::path dir = path.parent_path();
    if (!dir.empty() && !std::filesystem::exists(dir)) {
        std::filesystem::create_directories(dir);
    }
    std::ofstream f(file);
    f << data;
}

void CResourcesProvider::save(std::string file, std::shared_ptr<json> data) {
    save(std::move(file), CJsonUtil::to_string(std::move(data)));
}

std::shared_ptr<CAnimation> CAnimationProvider::getAnimation(const std::shared_ptr<CGame> &game,
                                                             const std::shared_ptr<CGameObject> &object, bool custom) {
    auto animation = game->createObject<CAnimation>("CAnimation");
    auto animationPath = object->getAnimation();
    if (std::filesystem::is_directory(animationPath)) {
        animation = game->createObject<CDynamicAnimation>("CDynamicAnimation");
    } else if (std::filesystem::is_regular_file(CResourcesProvider::getInstance()->getPath(animationPath + ".png"))) {
        animation = custom ? game->createObject<CAnimation>("CCustomAnimation")
                           : game->createObject<CStaticAnimation>("CStaticAnimation");
    } else {
        // TODO: if the path wasnt empty load text instead, requires changes in text
        // manager
        vstd::logger::warning("Loading empty animation");
    }
    animation->setObject(object);
    return animation;
}

std::shared_ptr<CAnimation> CAnimationProvider::getAnimation(const std::shared_ptr<CGame> &game, std::string path,
                                                             bool custom) {
    std::shared_ptr<CGameObject> object = game->createObject<CGameObject>();
    object->setAnimation(std::move(path));
    return getAnimation(game, object, custom);
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
    auto resolvedPath = CResourcesProvider::getInstance()->getPath(filePath);
    if (resolvedPath.empty()) {
        resolvedPath = filePath;
    }

    std::ifstream t(resolvedPath);
    return std::string(std::istreambuf_iterator<char>(t), std::istreambuf_iterator<char>());
}
