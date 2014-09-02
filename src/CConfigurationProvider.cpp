#include "CConfigurationProvider.h"
#include <QDebug>
#include <QFile>
#include <fstream>
#include <mutex>

Json::Value *CConfigurationProvider::getConfig ( std::string path ) {
	static std::mutex mutex;
	std::unique_lock<std::mutex> lock ( mutex );
	static CConfigurationProvider instance;
	return instance.getConfiguration ( path );
}

CConfigurationProvider::CConfigurationProvider() {}

CConfigurationProvider::~CConfigurationProvider() {
	for ( iterator it = begin(); it != end(); it++ ) {
		delete ( *it ).second;
	}
	clear();
}

Json::Value *CConfigurationProvider::getConfiguration ( std::string path ) {
	if ( this->find ( path ) != this->end() ) {
		return this->at ( path );
	}
	loadConfig ( path );
	return getConfiguration ( path );
}

void CConfigurationProvider::loadConfig ( std::string path ) {
	QFile file ( path.c_str() );
	Json::Value *config = new Json::Value();
	if ( file.open ( QIODevice::ReadOnly ) ) {
		Json::Reader reader;
		QByteArray data = file.readAll();
		std::string dataString = data.data();
		reader.parse ( dataString, *config );
		file.close();
		qDebug() << "Loaded configuration:" << path.c_str() << "\n";
	}
	this->insert ( std::pair<std::string, Json::Value *> ( path, config ) );
}