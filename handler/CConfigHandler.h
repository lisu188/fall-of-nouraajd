#pragma once
#include "CGlobal.h"

class CConfigHandler {
public:
    CConfigHandler ( std::set<QString> paths,CConfigHandler* parent=nullptr );
    QJsonObject getConfig ( QString type );
    std::set<QString> getAllTypes();
    bool isFlagSet ( QString type,QString property );
private:
    QJsonObject objectConfig;
    CConfigHandler *parent=nullptr;
};
