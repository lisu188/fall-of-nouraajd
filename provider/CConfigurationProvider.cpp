#include "CConfigurationProvider.h"
#include <QDebug>
#include "handler/CHandler.h"
#include "CResourcesProvider.h"

std::shared_ptr<QJsonObject> CConfigurationProvider::getConfig ( QString path ) {
    static CConfigurationProvider instance;
    return instance.getConfiguration ( path );
}

CConfigurationProvider::CConfigurationProvider() {

}

CConfigurationProvider::~CConfigurationProvider() {
    clear();
}

std::shared_ptr<QJsonObject> CConfigurationProvider::getConfiguration ( QString path ) {
    if ( this->find ( path ) != this->end() ) {
        return this->at ( path );
    }
    loadConfig ( path );
    return getConfiguration ( path );
}

void CConfigurationProvider::loadConfig ( QString path ) {
    std::shared_ptr<QFile> file =CResourcesProvider::getInstance()->getResource ( path );
    if ( file && file->open ( QIODevice::ReadOnly ) ) {
        QByteArray data = file->readAll();
        this->insert (  std::make_pair (
                            path,std::make_shared<QJsonObject>
                            ( QJsonDocument::fromJson ( data ).object() ) ) );
        file->close();
        qDebug() << "Loaded configuration:" << path << "\n";
    } else {
        qDebug ( ( "Cannot load file:"+ path ).toStdString().c_str() );
        this->insert ( std::make_pair ( path,std::make_shared<QJsonObject>() ) );
    }
}
