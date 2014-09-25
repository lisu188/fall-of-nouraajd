#include "CConfigurationProvider.h"
#include <QDebug>
#include <QFile>
#include <fstream>
#include <mutex>
#include <QJsonDocument>
#include "CResourcesHandler.h"

QJsonValue &CConfigurationProvider::getConfig ( QString path ) {
	static std::mutex mutex;
	std::unique_lock<std::mutex> lock ( mutex );
	static CConfigurationProvider instance;
	return instance.getConfiguration ( path );
}

CConfigurationProvider::CConfigurationProvider() {}

CConfigurationProvider::~CConfigurationProvider() {
	clear();
}

QJsonValue &CConfigurationProvider::getConfiguration ( QString path ) {
	if ( this->find ( path ) != this->end() ) {
		return this->at ( path );
	}
	loadConfig ( path );
	return getConfiguration ( path );
}

void CConfigurationProvider::loadConfig ( QString path ) {
	QFile *file =CResourcesHandler::getInstance()->getResource ( path );
	if ( file && file->open ( QIODevice::ReadOnly ) ) {
		QByteArray data = file->readAll();
		auto json=QJsonDocument::fromJson ( data );
		QJsonValue value;
		if ( json.isObject() ) {
			value=json.object();
		} else if ( json.isArray() ) {
			value=json.array();
		}
		this->insert ( std::pair<QString, QJsonValue > ( path,value ) );
		file->close();
		qDebug() << "Loaded configuration:" << path << "\n";
	} else {
		qDebug ( ( "Cannot load file:"+ path ).toStdString().c_str() );
		this->insert ( std::pair<QString, QJsonValue > ( path,QJsonValue() ) );
	}
}
