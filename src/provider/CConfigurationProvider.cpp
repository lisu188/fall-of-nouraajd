#include "CConfigurationProvider.h"
#include "handler/CHandler.h"

std::shared_ptr<Value> CConfigurationProvider::getConfig ( std::string path ) {
    static CConfigurationProvider instance;
    return instance.getConfiguration ( path );
}

CConfigurationProvider::CConfigurationProvider() {

}

CConfigurationProvider::~CConfigurationProvider() {
    clear();
}

std::shared_ptr<Value> CConfigurationProvider::getConfiguration ( std::string path ) {
    if ( this->find ( path ) != this->end() ) {
        return this->at ( path );
    }
    loadConfig ( path );
    return getConfiguration ( path );
}

void CConfigurationProvider::loadConfig ( std::string path ) {
    std::shared_ptr<QFile> file = CResourcesProvider::getInstance()->getResource ( path );
    if ( file && file->open ( QIODevice::ReadOnly ) ) {
        QByteArray data = file->readAll();
        this->insert ( std::make_pair (
                           path, std::make_shared<Value>
                           ( QJsonDocument::fromJson ( data ).object() ) ) );
        file->close();
        qDebug() << "Loaded configuration:" << path << "\n";
    } else {
        qDebug ( ( "Cannot load file:" + path ).toStdString().c_str() );
        this->insert ( std::make_pair ( path, std::make_shared<Value>() ) );
    }
}
