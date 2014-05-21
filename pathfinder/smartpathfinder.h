#ifndef SMARTPATHFINDER_H
#define SMARTPATHFINDER_H
#include "pathfinder.h"

class SmartPathFinder : public PathFinder
{
    Q_OBJECT
public:
    SmartPathFinder();
    SmartPathFinder(const SmartPathFinder &);

    // PathFinder interface
public:
    Coords findPath(Coords start, Coords goal);
};
Q_DECLARE_METATYPE(SmartPathFinder)
#endif // SMARTPATHFINDER_H
