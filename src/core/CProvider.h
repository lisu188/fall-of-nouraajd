#pragma once

#include "core/CGlobal.h"

enum CResType {
    CONFIG, MAP, PLUGIN, SAVE
};

class CAnimation;


class CResourcesProvider {
public:
    static CResourcesProvider *getInstance();

    std::string load(std::string path);

    std::shared_ptr<Value> loadJson(std::string path);

    std::string getPath(std::string path);

    std::set<std::string> getFiles(CResType type);

    void save(std::string file, std::string data);

    void save(std::string file, std::shared_ptr<Value> data);

private:
    static std::list<std::string> searchPath;

    CResourcesProvider();
};

class CConfigurationProvider : private std::map<std::string, std::shared_ptr<Value>> {
public:
    static std::shared_ptr<Value> getConfig(std::string path);

private:
    CConfigurationProvider();

    ~CConfigurationProvider();

    std::shared_ptr<Value> getConfiguration(std::string path);

    void loadConfig(std::string path);
};

class CAnimationProvider {
public:
    static std::shared_ptr<CAnimation> getAnimation(std::string path);
};