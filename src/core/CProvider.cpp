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
#include "core/CGame.h"
#include "core/CProvider.h"
#include "core/CJsonUtil.h"
#include "gui/CAnimation.h"

const std::string CResType::CONFIG = "CONFIG";
const std::string CResType::MAP = "MAP";
const std::string CResType::PLUGIN = "PLUGIN";
const std::string CResType::SAVE = "SAVE";

std::shared_ptr<json> CConfigurationProvider::getConfig(std::string path) {
    static CConfigurationProvider instance;
    return instance.getConfiguration(path);
}

CConfigurationProvider::CConfigurationProvider() {

}

CConfigurationProvider::~CConfigurationProvider() {
    clear();
}

std::shared_ptr<json> CConfigurationProvider::getConfiguration(std::string path) {
    if (this->find(path) != this->end()) {
        return this->at(path);
    }
    loadConfig(path);
    return getConfiguration(path);
}

void CConfigurationProvider::loadConfig(std::string path) {
    this->insert(std::make_pair(path, CResourcesProvider::getInstance()->loadJson(path)));
}

std::list<std::string> CResourcesProvider::searchPath = {""};

std::shared_ptr<CResourcesProvider> CResourcesProvider::getInstance() {
    static std::shared_ptr<CResourcesProvider> instance = std::make_shared<CResourcesProvider>();
    return instance;
}

std::string CResourcesProvider::load(std::string path) {
    std::ifstream t(getPath(path));
    return std::string(std::istreambuf_iterator<char>(t),
                       std::istreambuf_iterator<char>());
}

std::shared_ptr<json> CResourcesProvider::loadJson(std::string path) {
    return CJsonUtil::from_string(load(path));
}

std::string CResourcesProvider::getPath(std::string path) {
    for (auto it:searchPath) {
        if (boost::filesystem::exists(it / boost::filesystem::path(path))) {
            boost::filesystem::path p = it / boost::filesystem::path(path);
            return p.string();
        }
    }
    return std::string();
}

std::vector<std::string> CResourcesProvider::getFiles(std::string type) {
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

    boost::filesystem::directory_iterator dir(folderName), end;
    while (dir != end) {
        if (type == CResType::MAP || type == CResType::SAVE) {
            auto pt = dir->path().filename().stem().string();
            retValue.push_back(pt);
        } else {
            auto pt = dir->path().string();
            if (vstd::ends_with(pt, vstd::join({".", suffix}, ""))) {
                retValue.push_back(pt);
            }
        }
        dir++;
    }
    return retValue;
}

void CResourcesProvider::save(std::string file, std::string data) {
    vstd::logger::info("Saving map: " + file);
    boost::filesystem::path path(file);
    boost::filesystem::path dir = path.parent_path();
    if (!boost::filesystem::exists(dir)) {
        boost::filesystem::create_directory(dir);
    }
    std::ofstream f(file);
    f << data;
}

void CResourcesProvider::save(std::string file, std::shared_ptr<json> data) {
    save(file, CJsonUtil::to_string(data));
}

CResourcesProvider::CResourcesProvider() {

}

std::shared_ptr<CAnimation>
CAnimationProvider::getAnimation(std::shared_ptr<CGame> game, std::shared_ptr<CGameObject> object, bool custom) {
    auto ret = game->createObject<CAnimation>("CAnimation");
    if (boost::filesystem::is_directory(object->getAnimation())) {
        ret = game->createObject<CDynamicAnimation>("CDynamicAnimation");
    } else if (boost::filesystem::is_regular_file(
            CResourcesProvider::getInstance()->getPath(object->getAnimation() + ".png"))) {
        ret = custom ? game->createObject<CAnimation>("CCustomAnimation") : game->createObject<CStaticAnimation>(
                "CStaticAnimation");
    } else {
        //TODO: if the path wasnt empty load text instead
        vstd::logger::warning("Loading empty animation");
    }
    ret->setObject(object);
    return ret;
}

std::shared_ptr<CAnimation>
CAnimationProvider::getAnimation(std::shared_ptr<CGame> game, std::string path, bool custom) {
    std::shared_ptr<CGameObject> object = game->createObject<CGameObject>();
    object->setAnimation(path);
    return getAnimation(game, object, custom);
}
