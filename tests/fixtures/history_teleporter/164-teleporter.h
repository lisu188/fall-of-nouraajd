#include "building.h"

#ifndef TELEPORTER_H
#define TELEPORTER_H

class Teleporter : public Building
{
    Q_OBJECT
public:
    Teleporter();
    Teleporter(const Teleporter& teleporter);
    virtual void onEnter();
    virtual void onMove();
    bool canSave();
    Json::Value saveToJson();
    void loadFromJson(Json::Value config);
    void loadFromProps(Tmx::PropertySet set);
private:
    bool enabled=true;
};
Q_DECLARE_METATYPE(Teleporter)

#endif // TELEPORTER_H
