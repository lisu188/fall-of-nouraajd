#pragma once
#include <QObject>
#include <QFile>

class CResourcesHandler : public QObject {
	Q_OBJECT
public:
	static CResourcesHandler *getInstance();
	QFile *getResource ( QString path );
	QString getResourceAsString ( QString path );
private:
	CResourcesHandler();
};
