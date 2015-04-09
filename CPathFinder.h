#pragma once
#include "Util.h"
#include <functional>
#include <unordered_map>

class CCreature;

class CSmartPathFinder {
public:
	static Coords findNextStep  ( const Coords &start, const Coords &goal, std::function<bool ( const Coords& ) > canStep )  ;
private:
	static std::unordered_map<Coords, int> fillValues ( const Coords&  goal, const Coords&  start, std::function<bool ( const Coords& ) > canStep );
};
