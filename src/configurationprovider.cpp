#include "configurationprovider.h"
#include <QDebug>
#include <QFile>
#include <fstream>
#include <mutex>

Json::Value *ConfigurationProvider::getConfig ( std::string path ) {
	static std::mutex mutex;
	std::unique_lock<std::mutex> lock ( mutex );
	static ConfigurationProvider instance;
	return instance.getConfiguration ( path );
}

ConfigurationProvider::ConfigurationProvider() {}

ConfigurationProvider::~ConfigurationProvider() {
	for ( iterator it = begin(); it != end(); it++ ) {
		delete ( *it ).second;
	}
	clear();
}

Json::Value *ConfigurationProvider::getConfiguration ( std::string path ) {
	if ( this->find ( path ) != this->end() ) {
		return this->at ( path );
	}
	loadConfig ( path );
	return getConfiguration ( path );
}

void ConfigurationProvider::loadConfig ( std::string path ) {
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
