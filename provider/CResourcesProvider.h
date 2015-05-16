#pragma once
#include <QFile>
#include <QSet>
#include <QString>

enum CResType {
    CONFIG,MAP,SCRIPT,IMAGE
};

class CResourcesProvider : public QObject {
    Q_OBJECT
public:
    static CResourcesProvider *getInstance();
    QFile *getResource ( QString path );
    QString getResourceAsString ( QString path );
    QString getPath ( QString path );
    QSet<QString> getFiles ( CResType type );

private:
    static QList<QString> searchPath;
    CResourcesProvider();
};
