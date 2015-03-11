#pragma once
#include "object/CObject.h"
#include"CMap.h"
#include <QObject>
#include <QRunnable>
#include <unordered_map>
#include <unordered_set>

class IPathFinder {
public:
	virtual Coords findPath ( CCreature *first, CCreature *second ) =0;
};

class CDumbPathFinder : public IPathFinder {
public:
	virtual Coords findPath ( CCreature *first, CCreature *second ) override final;
};

class CRandomPathFinder : public IPathFinder {
public:
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

class CSmartPathFinder : public IPathFinder {
public:
	virtual Coords findPath ( CCreature *first, CCreature *second ) override final;
};
