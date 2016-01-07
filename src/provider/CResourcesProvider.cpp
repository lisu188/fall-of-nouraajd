#include "CResourcesProvider.h"
#include "core/CUtil.h"


std::list<std::string> CResourcesProvider::searchPath = {"", ":/"};

CResourcesProvider *CResourcesProvider::getInstance() {
    static CResourcesProvider instance;
    return &instance;
}

std::shared_ptr<QFile> CResourcesProvider::getResource ( std::string path ) {
    path = getPath ( path );
    std::shared_ptr<QFile> ptr ( new QFile ( path ) );
    if ( ptr->exists() ) {
        return ptr;
    }
    return nullptr;
}

std::string CResourcesProvider::load ( std::string path ) {
    std::shared_ptr<QFile> file = getResource ( path );
    if ( file && file->open ( QIODevice::ReadOnly ) ) {
        QByteArray data = file->readAll();
        QByteArray uncompressed = qUncompress ( data );
        if ( uncompressed.size() ) {
            return std::string::fromUtf8 ( uncompressed );
        }
        return std::string::fromUtf8 ( data );
    }
    return std::string();
}

std::string CResourcesProvider::getPath ( std::string path ) {
    for ( auto it:searchPath ) {
        QFile fileRes ( it + path );
        if ( fileRes.exists() ) {
            return it + path;
        }
    }
    return std::string();
}

std::set<std::string> CResourcesProvider::getFiles ( CResType type ) {
    std::set<std::string> retValue;
    std::string folderName;
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

void CResourcesProvider::save ( std::string file, QByteArray data ) {
    QFile f ( file );
    QFileInfo info ( f );
    QDir::root().mkpath ( info.absoluteDir().path() );
    if ( f.open ( QIODevice::WriteOnly ) ) {
        f.write ( data );
    } else {
        vstd::fail ( "Failed saving!" );
    }
}

void CResourcesProvider::save ( std::string file, std::string data ) {
    save ( file, data.toUtf8() );
}

void CResourcesProvider::save ( std::string file, std::shared_ptr<Value> data ) {
    save ( file, QJsonDocument ( *data ).toJson ( QJsonDocument::JsonFormat::Compact ) );
}

void CResourcesProvider::saveZip ( std::string file, QByteArray data ) {
    save ( file, qCompress ( data, 9 ) );
}

void CResourcesProvider::saveZip ( std::string file, std::string data ) {
    saveZip ( file, data.toUtf8() );
}

void CResourcesProvider::saveZip ( std::string file, std::shared_ptr<Value> data ) {
    saveZip ( file, QJsonDocument ( *data ).toJson ( QJsonDocument::JsonFormat::Compact ) );
}

CResourcesProvider::CResourcesProvider() {

}
