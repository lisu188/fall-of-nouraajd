#include "pathfindercache.h"
#include <QDebug>

PathFinderCache::PathFinderCache() {
}

PathFinderCache &PathFinderCache::getInstance() {
    static PathFinderCache    instance;
    return instance;
}

void PathFinderCache::setPath(std::vector<Cell> path) {
	this->path = path;
    qDebug()<<"Setting path in cache.";
    for(int i=0;i<path.size();i++){
        qDebug()<<path.at(i).x<<path.at(i).y;
    }
}

std::vector<Cell> PathFinderCache::getPath() {
	return path;
}

Cell::Cell(int x, int y, Coords goal)
		: x(x), y(y), goal(goal) {
}

bool CellCompare::operator()(const Cell &a, const Cell &b) {
	int dista = sqrt(
	        (a.x - a.goal.x) * (a.x - a.goal.x)
	                + (a.y - a.goal.y) * (a.y - a.goal.y));
	int distb = sqrt(
	        (b.x - b.goal.x) * (b.x - b.goal.x)
	                + (b.y - b.goal.y) * (b.y - b.goal.y));
	if (dista != distb)
		return dista < distb;
	if (a.x != b.x)
		return a.x < b.x;
	return a.y < b.y;
}
