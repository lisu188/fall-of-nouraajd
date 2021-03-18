/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

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

#include "core/CGlobal.h"
#include "gui/CAnimation.h"

struct CResType {
    const static std::string CONFIG;
    const static std::string MAP;
    const static std::string PLUGIN;
    const static std::string SAVE;
    const static std::string IMAGE;
};

class CResource : public CGameObject {
V_META(CResource, CGameObject, vstd::meta::empty())
public:
    virtual std::string type() = 0;

    const std::string &getPath() const;

    void setPath(const std::string &path);

    const std::string &getPathPrefix() const;

    void setPathPrefix(const std::string &pathPrefix);

    const std::string &getPathSuffix() const;

    void setPathSuffix(const std::string &pathSuffix);

private:
    std::string path;
    std::string pathPrefix;
    std::string pathSuffix;
};

class CTextResource : public CResource {
V_META(CTextResource, CResource, vstd::meta::empty())
public:
    std::string getText();
};

class CConfigResource : public CResource {
V_META(CConfigResource, CTextResource, vstd::meta::empty())
public:
    std::string type() override {
        return CResType::CONFIG;
    }
};

class CResourceLoader : public CGameObject {
V_META(CResourceLoader, CGameObject, vstd::meta::empty())
public:
    virtual std::shared_ptr<CResource> load(std::string path) = 0;
};

class CConfigResourceLoader : public CResourceLoader {
V_META(CConfigResourceLoader, CResourceLoader, vstd::meta::empty())
public:
    std::shared_ptr<CResource> load(std::string path) override {
        auto config = std::make_shared<CConfigResource>();
        config->setPathPrefix("config");
        config->setPath(path);
        config->setPathSuffix("json");
        return config;
    }
};


class CAnimation;

class CGame;

class CGameObject;

class CResourcesProvider {
public:
    static std::shared_ptr<CResourcesProvider> getInstance();

    std::string load(std::string path);

    std::shared_ptr<json> loadJson(std::string path);

    std::string getPath(std::string path);

    std::vector<std::string> getFiles(const std::string &type);

    void save(std::string file, const std::string &data);

    void save(std::string file, std::shared_ptr<json> data);

    CResourcesProvider() = default;

private:
    static std::list<std::string> searchPath;
};

class CConfigurationProvider : private std::map<std::string, std::shared_ptr<json>> {
public:
    static std::shared_ptr<json> getConfig(const std::string &path);

private:
    CConfigurationProvider() = default;

    ~CConfigurationProvider();

    std::shared_ptr<json> getConfiguration(const std::string &path);

    void loadConfig(const std::string &path);
};

class CAnimationProvider {
public:
    static std::shared_ptr<CAnimation>
    getAnimation(const std::shared_ptr<CGame> &game, const std::shared_ptr<CGameObject> &object, bool custom = false);

    static std::shared_ptr<CAnimation>
    getAnimation(const std::shared_ptr<CGame> &game, std::string path, bool custom = false);
};