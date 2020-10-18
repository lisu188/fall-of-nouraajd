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

    std::vector<std::string> getFiles(std::string type);

    void save(std::string file, std::string data);

    void save(std::string file, std::shared_ptr<json> data);

    CResourcesProvider();

private:
    static std::list<std::string> searchPath;
};

class CConfigurationProvider : private std::map<std::string, std::shared_ptr<json>> {
public:
    static std::shared_ptr<json> getConfig(std::string path);

private:
    CConfigurationProvider();

    ~CConfigurationProvider();

    std::shared_ptr<json> getConfiguration(std::string path);

    void loadConfig(std::string path);
};

class CAnimationProvider {
public:
    static std::shared_ptr<CAnimation>
    getAnimation(std::shared_ptr<CGame> game, std::shared_ptr<CGameObject> object, bool custom = false);

    static std::shared_ptr<CAnimation> getAnimation(std::shared_ptr<CGame> game, std::string path, bool custom = false);
};