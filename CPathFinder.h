#pragma once
#include "Util.h"
#include <functional>

class CCreature;

class CSmartPathFinder {
public:
	static Coords findPath  ( Coords  start, Coords  goal,std::function<bool ( const Coords& ) > canStep )  ;
};
