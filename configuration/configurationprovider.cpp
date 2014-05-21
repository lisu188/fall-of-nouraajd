#include "configurationprovider.h"
#include <QDebug>
#include <QFile>
#include <fstream>

ConfigurationProvider *ConfigurationProvider::instance=0;

Json::Value *ConfigurationProvider::getConfig(std::string path)
{
    if(path.find(":/")==std::string::npos) {
        path=":/"+path;
    }
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
    QFile file(path.c_str());
    Json::Value *config=new Json::Value();
    if(file.open(QIODevice::ReadOnly))
    {
        Json::Reader reader;
        QByteArray data=file.readAll();
        std::string dataString=data.data();
        reader.parse( dataString, *config );
        file.close();
        qDebug() << "Loaded configuration:" << path.c_str()<<"\n";
    }
    this->insert(std::pair<std::string,Json::Value*>(path,config));
}
