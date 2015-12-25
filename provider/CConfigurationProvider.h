#pragma once

#include "core/CGlobal.h"

class CConfigurationProvider : private std::map<QString, std::shared_ptr<QJsonObject>> {
public:
    static std::shared_ptr<QJsonObject> getConfig ( QString path );

private:
    CConfigurationProvider();

    ~CConfigurationProvider();

    std::shared_ptr<QJsonObject> getConfiguration ( QString path );

    void loadConfig ( QString path );
};
