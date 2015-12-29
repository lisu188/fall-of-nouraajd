#pragma once

#include "core/CGlobal.h"

enum CResType {
    CONFIG, MAP, SCRIPT, IMAGE, SAVE
};

class CResourcesProvider {
public:
    static CResourcesProvider *getInstance();

    std::shared_ptr<QFile> getResource ( QString path );

    QString load ( QString path );

    QString getPath ( QString path );

    std::set<QString> getFiles ( CResType type );

    void save ( QString file, QByteArray data );

    void save ( QString file, QString data );

    void save ( QString file, std::shared_ptr<QJsonObject> data );

    void save ( QString file, std::shared_ptr<QJsonArray> data );

    void saveZip ( QString file, QByteArray data );

    void saveZip ( QString file, QString data );

    void saveZip ( QString file, std::shared_ptr<QJsonObject> data );

    void saveZip ( QString file, std::shared_ptr<QJsonArray> data );

private:
    static QList<QString> searchPath;

    CResourcesProvider();
};
