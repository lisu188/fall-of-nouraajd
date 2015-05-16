#include "CResourcesProvider.h"
#include <QDirIterator>
#include <QSet>
#include <QList>
#include <QString>

QList<QString> CResourcesProvider::searchPath= {"",":/"};

CResourcesProvider *CResourcesProvider::getInstance() {
    static CResourcesProvider instance;
    return &instance;
}

QFile *CResourcesProvider::getResource ( QString path ) {
    path=getPath ( path );
    QFile fileSys ( path );
    if ( fileSys.exists() ) {
        return new QFile ( path,this );
    }
    return nullptr;
}

QString CResourcesProvider::getResourceAsString ( QString path ) {
    QFile *file=getResource ( path );
    if ( file && file->open ( QIODevice::ReadOnly ) ) {
        return QString ( file->readAll() );
    }
    return QString();
}

QString CResourcesProvider::getPath ( QString path ) {
    for ( auto it:searchPath ) {
        QFile fileRes ( it+path );
        if ( fileRes.exists() ) {
            return it+path;
        }
    }
    return QString();
}

QSet<QString> CResourcesProvider::getFiles ( CResType type ) {
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

CResourcesProvider::CResourcesProvider() {

}
