#include <map/coords.h>
#include <vector>

#ifndef PATHFINDERCACHE_H
#define PATHFINDERCACHE_H

class Cell {
    public:
        int x, y;
        Coords goal;
        Cell(int x, int y, Coords goal);
};

class CellCompare {
    public:
        bool operator()(const Cell &a, const Cell &b);
};

class PathFinderCache
{
private:
    PathFinderCache();
    std::vector<Cell> path;
public:
    static PathFinderCache &getInstance();
    void setPath(std::vector<Cell> path);
    std::vector<Cell> getPath();
};

#endif // PATHFINDERCACHE_H
