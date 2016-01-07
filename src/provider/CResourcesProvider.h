#pragma once

#include "core/CGlobal.h"

enum CResType {
    CONFIG, MAP, SCRIPT, IMAGE, SAVE
};

class CResourcesProvider {
public:
    static CResourcesProvider *getInstance();

    std::shared_ptr<QFile> getResource ( std::string path );

    std::string load ( std::string path );

    std::string getPath ( std::string path );

    std::set<std::string> getFiles ( CResType type );

    void save ( std::string file, QByteArray data );

    void save ( std::string file, std::string data );

    void save ( std::string file, std::shared_ptr<Value> data );

    void saveZip ( std::string file, QByteArray data );

    void saveZip ( std::string file, std::string data );

    void saveZip ( std::string file, std::shared_ptr<Value> data );

private:
    static std::list<std::string> searchPath;

    CResourcesProvider();
};
