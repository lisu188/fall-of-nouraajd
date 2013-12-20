#include "configurationprovider.h"
#include <QDebug>
#include <fstream>

ConfigurationProvider *ConfigurationProvider::instance=0;

Json::Value *ConfigurationProvider::getConfig(std::string path)
{
    if(!instance)
    {
        instance=new ConfigurationProvider();
    }
    return instance->getConfiguration(path);
}

void ConfigurationProvider::terminate()
{
    delete instance;
}

ConfigurationProvider::ConfigurationProvider()
{
}

ConfigurationProvider::~ConfigurationProvider()
{
    for(iterator it=begin(); it!=end(); it++)
    {
        delete (*it).second;
    }
    clear();
}

Json::Value *ConfigurationProvider::getConfiguration(std::string path)
{
    if(this->find(path)!=this->end()) {
        return this->at(path);
    }
    loadConfig(path);
    return getConfiguration(path);
}

void ConfigurationProvider::loadConfig(std::string path)
{
    Json::Value *config=new Json::Value();
    std::fstream jsonFileStream;
    jsonFileStream.open (path);
    Json::Reader reader;
    reader.parse( jsonFileStream, *config );
    jsonFileStream.close();
    this->insert(std::pair<std::string,Json::Value*>(path,config));
    qDebug() << "Loaded configuration:" << path.c_str()<<"\n";
}
