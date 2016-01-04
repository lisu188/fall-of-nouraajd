#pragma once

#include "core/CGlobal.h"

class CConfigurationProvider : private std::map<std::string, std::shared_ptr<Value>> {
public:
    static std::shared_ptr<Value> getConfig ( std::string path );

private:
    CConfigurationProvider();

    ~CConfigurationProvider();

    std::shared_ptr<Value> getConfiguration ( std::string path );

    void loadConfig ( std::string path );
};
