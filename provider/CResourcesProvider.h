#pragma once
#include "CGlobal.h"

enum CResType {
    CONFIG,MAP,SCRIPT,IMAGE
};

class CResourcesProvider {
public:
    static CResourcesProvider *getInstance();
    std::shared_ptr<QFile> getResource( QString path );
    QString getResourceAsString ( QString path );
    QString getPath ( QString path );
    std::set<QString> getFiles ( CResType type );

private:
    static QList<QString> searchPath;
    CResourcesProvider();
};
