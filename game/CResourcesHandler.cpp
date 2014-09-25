#include "CResourcesHandler.h"


CResourcesHandler *CResourcesHandler::getInstance() {
	static CResourcesHandler instance;
	return &instance;
}

QFile *CResourcesHandler::getResource ( QString path ) {
	QFile fileSys ( path );
	if ( fileSys.exists() ) {
		return new QFile ( path,this );
	}
	QFile fileRes ( ":/"+path );
	if ( fileRes.exists() ) {
		return new QFile ( ":/"+path,this );
	}
	return NULL;
}

QString CResourcesHandler::getResourceAsString ( QString path ) {
	QFile *file=getResource ( path );
	if ( file && file->open ( QIODevice::ReadOnly ) ) {
		return QString ( file->readAll() );
	}
	return QString();
}

QString CResourcesHandler::getPath ( QString path ) {
	QFile fileSys ( path );
	if ( fileSys.exists() ) {
		return  path;
	}
	QFile fileRes (  ":/"+path );
	if ( fileRes.exists() ) {
		return ":/"+path;
	}
	return QString();
}

CResourcesHandler::CResourcesHandler() {

}
