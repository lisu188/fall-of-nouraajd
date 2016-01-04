#pragma once

#include "core/CGlobal.h"

class CConfigurationProvider : private std::map<std::string, std::shared_ptr<QJsonObject>> {
public:
    static std::shared_ptr<QJsonObject> getConfig ( std::string path );

private:
    CConfigurationProvider();

    ~CConfigurationProvider();

    std::shared_ptr<QJsonObject> getConfiguration ( std::string path );

    void loadConfig ( std::string path );
};
