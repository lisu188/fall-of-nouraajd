#ifndef CONFIGURATIONPROVIDER_H
#define CONFIGURATIONPROVIDER_H
#include <lib/json/json.h>
#include <string>

class ConfigurationProvider : private std::map<std::string, Json::Value*>
{
public:
    static Json::Value* getConfig(std::string path);
    static void terminate();
private:
    ConfigurationProvider();
    ~ConfigurationProvider();
    static ConfigurationProvider *instance;
    Json::Value * getConfiguration(std::string path);
    void loadConfig(std::string path);

};

#endif // CONFIGURATIONPROVIDER_H
