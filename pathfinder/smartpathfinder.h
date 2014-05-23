#ifndef SMARTPATHFINDER_H
#define SMARTPATHFINDER_H
#include "pathfinder.h"
#include <unordered_map>
#include <unordered_set>

class Cell{
public:
    int x,y;
    Coords goal;
    Cell(int x,int y,Coords goal):x(x),y(y),goal(goal){}
    Coords toCoords(){
        return Coords(x,y,goal.z);
    }
};

class SmartPathFinder : public PathFinder
{
    Q_OBJECT
public:
    SmartPathFinder();
    SmartPathFinder(const SmartPathFinder &);

    // PathFinder interface
public:
    Coords findPath(Coords start, Coords goal);
private:
    int getCost(Coords coords);
    std::list<Coords> getNearCells(Coords coords);
    std::unordered_map<Coords,int,CoordsHasher> values;
    Coords getNearestCell(Coords start);
    void processNode(Coords start, std::list<Cell> &nodes, std::unordered_set<Coords,CoordsHasher> &marked);
    bool canStep(int x,int y ,int z);
};
Q_DECLARE_METATYPE(SmartPathFinder)
#endif // SMARTPATHFINDER_H
