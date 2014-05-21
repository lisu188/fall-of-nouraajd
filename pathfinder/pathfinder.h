#ifndef PATHFINDER_H
#define PATHFINDER_H
#include <map/coords.h>
#include <QObject>

class PathFinder: public QObject {
	public:
		PathFinder();
		virtual Coords findPath(Coords start, Coords goal)=0;
};

#endif // PATHFINDER_H