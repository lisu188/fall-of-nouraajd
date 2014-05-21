#include "pathfinder.h"

#ifndef DUMBPATHFINDER_H
#define DUMBPATHFINDER_H

class DumbPathFinder: public PathFinder {
		Q_OBJECT
	public:
		DumbPathFinder();
		DumbPathFinder(const DumbPathFinder &);

		// PathFinder interface
	public:
		Coords findPath(Coords start, Coords goal);
};
Q_DECLARE_METATYPE(DumbPathFinder)
#endif // DUMBPATHFINDER_H