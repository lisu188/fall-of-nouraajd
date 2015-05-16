#ifndef CONFIGURATIONPROVIDER_H
#define CONFIGURATIONPROVIDER_H
#include <string>
#include <QJsonValue>
#include <QJsonArray>
#include <QJsonObject>
#include <QJsonDocument>
#include "map"
class CConfigurationProvider : private std::map<QString, QJsonValue > {
public:
    static QJsonValue& getConfig ( QString path );
private:
    CConfigurationProvider();
    ~CConfigurationProvider();
    QJsonValue &getConfiguration ( QString path );
    void loadConfig ( QString path );
};

#endif // CONFIGURATIONPROVIDER_H
