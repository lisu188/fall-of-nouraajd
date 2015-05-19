#pragma once
#include "CGlobal.h"
class CConfigurationProvider : private std::map<QString, QJsonValue > {
public:
    static QJsonValue& getConfig ( QString path );
private:
    CConfigurationProvider();
    ~CConfigurationProvider();
    QJsonValue &getConfiguration ( QString path );
    void loadConfig ( QString path );
};
