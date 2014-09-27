#ifndef PATHFINDER_H
#define PATHFINDER_H
#include "CCreature.h"

#include"CMap.h"
#include <QObject>
#include <QRunnable>
#include <unordered_map>
#include <unordered_set>

class APathFinder : public QObject {
	Q_OBJECT
public:
	virtual Coords findPath ( CCreature *first, CCreature *second ) =0;
};

class CDumbPathFinder : public APathFinder {
	Q_OBJECT
public:
	CDumbPathFinder();
	CDumbPathFinder ( const CDumbPathFinder & );
	Coords findPath ( CCreature *first, CCreature *second );
};

class CRandomPathFinder : public APathFinder {
	Q_OBJECT
public:
	CRandomPathFinder();
	CRandomPathFinder ( const CRandomPathFinder & );
	Coords findPath ( CCreature *, CCreature * );
};

class Cell {
public:
	int x, y;
	Coords goal;
	Cell ( int x, int y, Coords goal ) : x ( x ), y ( y ), goal ( goal ) {}
	Coords toCoords() { return Coords ( x, y, goal.z ); }
};

class CSmartPathFinder : public APathFinder {
	Q_OBJECT
public:
	CSmartPathFinder();
	CSmartPathFinder ( const CSmartPathFinder & );
	Coords findPath ( CCreature *first, CCreature *second );
private:
	int getCost ( Coords coords );
	std::list<Coords> getNearCells ( Coords coords );
	std::unordered_map<Coords, int, CoordsHasher> values;
	Coords getNearestCell ( Coords start );
	void processNode ( CCreature *first, std::list<Cell> &nodes,
	                   std::unordered_set<Coords, CoordsHasher> &marked );
	bool canStep ( CMap *map, int x, int y, int z );
};

class CompletionListener : public QObject {
	Q_OBJECT
public:
	static CompletionListener *getInstance();
	void start();
	void stop();
	bool isCompleted();
	void run();
	void registerWorker();
	void deregisterWorker();
	Q_SIGNAL void completed();
private:
	int workers;
	bool started;
};

class PathFinderWorker : public QObject, public QRunnable {
	Q_OBJECT
public:
	PathFinderWorker ( CCreature *first, CCreature *second, APathFinder *finder );
	void run();

private:
	Q_SIGNAL void completed ( int x, int y );
	Q_SIGNAL void started();
	Q_SIGNAL void ended();
	CCreature *first;
	CCreature *second;
	APathFinder *finder;
};
#endif // PATHFINDER_H
