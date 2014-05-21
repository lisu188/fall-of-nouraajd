#ifndef RANDOMPATHFINDER_H
#define RANDOMPATHFINDER_H
#include "pathfinder.h"

class RandomPathFinder: public PathFinder {
		Q_OBJECT
	public:
		RandomPathFinder();
		RandomPathFinder(const RandomPathFinder &);
		// PathFinder interface
	public:
		Coords findPath(Coords, Coords);
};
Q_DECLARE_METATYPE(RandomPathFinder)
#endif // RANDOMPATHFINDER_H