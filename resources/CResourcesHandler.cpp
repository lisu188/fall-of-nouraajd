#include "CResourcesHandler.h"


CResourcesHandler *CResourcesHandler::getInstance() {
	static CResourcesHandler instance;
	return &instance;
}

QFile *CResourcesHandler::getResource ( QString path ) {
	QFile fileSys ( path );
	if ( fileSys.open ( QIODevice::ReadOnly ) ) {
		return new QFile ( path,this );
	}
	QFile fileRes ( ":/"+path );
	if ( fileRes.open ( QIODevice::ReadOnly ) ) {
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

CResourcesHandler::CResourcesHandler() {

}
