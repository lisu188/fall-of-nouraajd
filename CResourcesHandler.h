#pragma once
#include <QObject>
#include <QFile>
#include <QSet>
#include <QString>

enum CResType {
	CONFIG,MAP,SCRIPT,IMAGE
};

class CResourcesHandler : public QObject {
	Q_OBJECT
public:
	static CResourcesHandler *getInstance();
	QFile *getResource ( QString path );
	QString getResourceAsString ( QString path );
	QString getPath ( QString path );
	QSet<QString> getFiles ( CResType type );

private:
	static QList<QString> searchPath;
	CResourcesHandler();
};
