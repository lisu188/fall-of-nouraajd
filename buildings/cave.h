#ifndef CAVE_H
#define CAVE_H
#include "building.h"

class Cave : public Building
{
    Q_OBJECT
public:
    Cave();
    Cave(const Cave& cave);
    Cave(int x, int y,int z);
    virtual void onEnter();
    virtual void onMove();
    bool canSave();

private:
    bool enabled;
};
Q_DECLARE_METATYPE(Cave)

#endif // CAVE_H
