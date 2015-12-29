#include "CResourcesProvider.h"
#include "core/CUtil.h"
#include "vstd.h"

QList<QString> CResourcesProvider::searchPath = {"", ":/"};

CResourcesProvider *CResourcesProvider::getInstance() {
    static CResourcesProvider instance;
    return &instance;
}

std::shared_ptr<QFile> CResourcesProvider::getResource ( QString path ) {
    path = getPath ( path );
    std::shared_ptr<QFile> ptr ( new QFile ( path ) );
    if ( ptr->exists() ) {
        return ptr;
    }
    return nullptr;
}

QString CResourcesProvider::load ( QString path ) {
    std::shared_ptr<QFile> file = getResource ( path );
    if ( file && file->open ( QIODevice::ReadOnly ) ) {
        QByteArray data = file->readAll();
        QByteArray uncompressed = qUncompress ( data );
        if ( uncompressed.size() ) {
            return QString::fromUtf8 ( uncompressed );
        }
        return QString::fromUtf8 ( data );
    }
    return QString();
}

QString CResourcesProvider::getPath ( QString path ) {
    for ( auto it:searchPath ) {
        QFile fileRes ( it + path );
        if ( fileRes.exists() ) {
            return it + path;
        }
    }
    return QString();
}

std::set<QString> CResourcesProvider::getFiles ( CResType type ) {
    std::set<QString> retValue;
    QString folderName;
    QDirIterator::IteratorFlag flag = QDirIterator::NoIteratorFlags;
    switch ( type ) {
    case CONFIG:
        folderName = "config";
        flag = QDirIterator::Subdirectories;
        break;
    case SCRIPT:
        folderName = "scripts";
        break;
    case IMAGE:
        folderName = "images";
        flag = QDirIterator::Subdirectories;
        break;
    case MAP:
        folderName = "maps";
        break;
    case SAVE:
        folderName = "save";
        break;
    }
    for ( auto it = searchPath.begin(); it != searchPath.end(); it++ ) {
        QDirIterator dirIt ( *it + folderName, flag );
        while ( dirIt.hasNext() ) {
            dirIt.next();
            retValue.insert ( dirIt.filePath() );
        }
    }
    return retValue;
}

void CResourcesProvider::save ( QString file, QByteArray data ) {
    QFile f ( file );
    QFileInfo info ( f );
    QDir::root().mkpath ( info.absoluteDir().path() );
    if ( f.open ( QIODevice::WriteOnly ) ) {
        f.write ( data );
    } else {
        vstd::fail ( "Failed saving!" );
    }
}

void CResourcesProvider::save ( QString file, QString data ) {
    save ( file, data.toUtf8() );
}

void CResourcesProvider::save ( QString file, std::shared_ptr<QJsonObject> data ) {
    save ( file, QJsonDocument ( *data ).toJson ( QJsonDocument::JsonFormat::Compact ) );
}

void CResourcesProvider::save ( QString file, std::shared_ptr<QJsonArray> data ) {
    save ( file, QJsonDocument ( *data ).toJson ( QJsonDocument::JsonFormat::Compact ) );
}

void CResourcesProvider::saveZip ( QString file, QByteArray data ) {
    save ( file, qCompress ( data, 9 ) );
}

void CResourcesProvider::saveZip ( QString file, QString data ) {
    saveZip ( file, data.toUtf8() );
}

void CResourcesProvider::saveZip ( QString file, std::shared_ptr<QJsonObject> data ) {
    saveZip ( file, QJsonDocument ( *data ).toJson ( QJsonDocument::JsonFormat::Compact ) );
}

void CResourcesProvider::saveZip ( QString file, std::shared_ptr<QJsonArray> data ) {
    saveZip ( file, QJsonDocument ( *data ).toJson ( QJsonDocument::JsonFormat::Compact ) );
}

CResourcesProvider::CResourcesProvider() {

}
