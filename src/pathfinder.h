#ifndef PATHFINDER_H
#define PATHFINDER_H
#include <src/map.h>
#include <QObject>
#include <unordered_map>
#include <unordered_set>

class PathFinder: public QObject
{
public:
    PathFinder();
    virtual Coords findPath(Coords start, Coords goal) = 0;
};

class DumbPathFinder : public PathFinder
{
    Q_OBJECT
public:
    DumbPathFinder();
    DumbPathFinder(const DumbPathFinder &);

    // PathFinder interface
public:
    Coords findPath(Coords start, Coords goal);
};
Q_DECLARE_METATYPE(DumbPathFinder)

class RandomPathFinder : public PathFinder
{
    Q_OBJECT
public:
    RandomPathFinder();
    RandomPathFinder(const RandomPathFinder &);
    // PathFinder interface
public:
    Coords findPath(Coords, Coords);
};
Q_DECLARE_METATYPE(RandomPathFinder)

class Cell
{
public:
    int x, y;
    Coords goal;
    Cell(int x, int y, Coords goal): x(x), y(y), goal(goal) {}
    Coords toCoords()
    {
        return Coords(x, y, goal.z);
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
    std::unordered_map<Coords, int, CoordsHasher> values;
    Coords getNearestCell(Coords start);
    void processNode(Coords start, std::list<Cell> &nodes, std::unordered_set<Coords, CoordsHasher> &marked);
    bool canStep(int x, int y , int z);
};
Q_DECLARE_METATYPE(SmartPathFinder)
#endif // PATHFINDER_H
