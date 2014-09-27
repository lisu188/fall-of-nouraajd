#include "CResourcesHandler.h"
#include <QDirIterator>
QList<QString> CResourcesHandler::searchPath= {"",":/"};

CResourcesHandler *CResourcesHandler::getInstance() {
	static CResourcesHandler instance;
	return &instance;
}

QFile *CResourcesHandler::getResource ( QString path ) {
	path=getPath ( path );
	QFile fileSys ( path );
	if ( fileSys.exists() ) {
		return new QFile ( path,this );
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
	for ( auto it=searchPath.begin(); it!=searchPath.end(); it++ ) {
		QFile fileRes ( *it+path );
		if ( fileRes.exists() ) {
			return *it+path;
		}
	}
	return QString();
}

QSet<QString> CResourcesHandler::getFiles ( CResType type ) {
	QSet<QString> retValue;
	QString folderName;
	QDirIterator::IteratorFlag flag=QDirIterator::NoIteratorFlags;
	switch ( type ) {
	case CONFIG:
		folderName="config";
		flag=QDirIterator::Subdirectories ;
		break;
	case SCRIPT:
		folderName="scripts";
		break;
	case IMAGE:
		folderName="images";
		flag=QDirIterator::Subdirectories ;
		break;
	case MAP:
		folderName="maps";
		break;
	}
	for ( auto it=searchPath.begin(); it!=searchPath.end(); it++ ) {
		QDirIterator dirIt ( *it +folderName ,flag );
		while ( dirIt.hasNext() ) {
			dirIt.next();
			retValue.insert ( dirIt.filePath() );
		}
	}
	return retValue;
}

CResourcesHandler::CResourcesHandler() {

}
