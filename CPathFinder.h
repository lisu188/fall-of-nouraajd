#pragma once
#include "CCreature.h"
#include"CMap.h"
#include <QObject>
#include <QRunnable>
#include <unordered_map>
#include <unordered_set>
#define MOVE_TIMEOUT 500

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
	virtual Coords findPath ( CCreature *first, CCreature *second ) override final;
};

class CRandomPathFinder : public APathFinder {
	Q_OBJECT
public:
	CRandomPathFinder();
	CRandomPathFinder ( const CRandomPathFinder & );
	virtual Coords findPath ( CCreature *, CCreature * ) override final;
};

class Cell {
public:
	int x, y;
	Coords goal;
	Cell ( int x, int y, Coords goal ) : x ( x ), y ( y ), goal ( goal ) {

	}
	Coords toCoords() {
		return Coords ( x, y, goal.z );
	}
};

class CSmartPathFinder : public APathFinder {
	Q_OBJECT
public:
	CSmartPathFinder();
	CSmartPathFinder ( const CSmartPathFinder & );
	virtual Coords findPath ( CCreature *first, CCreature *second ) override final;
private:
	int getCost ( Coords coords );
	std::list<Coords> getNearCells ( Coords coords );
	std::unordered_map<Coords, int> values;
	Coords getNearestCell ( Coords start );
	void processNode ( CCreature *first, std::list<Cell> &nodes,
	                   std::unordered_set<Coords> &marked );
};
