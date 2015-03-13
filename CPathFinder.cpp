#include "CPathFinder.h"
#include"CMap.h"
#include "object/CObject.h"

#include <math.h>
#include <unordered_map>
#include <unordered_set>

static inline bool cellCompare ( const Coords &a, const Coords &b , const Coords &goal ) {
	float dista = sqrt ( ( a.x - goal.x ) * ( a.x - goal.x ) +
	                     ( a.y - goal.y ) * ( a.y - goal.y ) );
	float distb = sqrt ( ( b.x - goal.x ) * ( b.x - goal.x ) +
	                     ( b.y - goal.y ) * ( b.y - goal.y ) );
	return dista < distb;
}

static inline std::list<Coords> getNearCells ( const Coords coords ,const std::unordered_map<Coords, int> values ) {
	std::list<Coords> list;
	for ( int i = -1; i <= 1; i++ )
		for ( int j = -1; j <= 1; j++ ) {
			if ( i != 0 && j != 0 ) {
				continue;
			}
			if ( i == 0 && j == 0 ) {
				continue;
			}
			Coords x ( coords.x + i, coords.y + j, coords.z ) ;
			if ( values.find ( x ) !=
			        values.end() ) {
				list.push_back ( x );
			}
		}
	return list;
}

static inline std::list<Coords> getNearCells ( Coords coords ) {
	std::list<Coords> list;
	for ( int i = -1; i <= 1; i++ )
		for ( int j = -1; j <= 1; j++ ) {
			if ( i != 0 && j != 0 ) {
				continue;
			}
			if ( i == 0 && j == 0 ) {
				continue;
			}
			list.push_back ( Coords ( coords.x + i, coords.y + j, coords.z ) );
		}
	return list;
}

static inline Coords getNearestCell ( Coords start ,std::unordered_map<Coords, int> &values ) {
	std::list<Coords> list = getNearCells ( start,values );
	if ( list.size() == 0 ) {
		return start;
	}
	int curCost = values.find ( *list.begin() )->second;
	Coords curCell = *list.begin();
	for ( std::list<Coords>::iterator it = list.begin(); it != list.end(); it++ ) {
		int tmpCost =values.find ( *it )->second;
		if ( tmpCost < curCost ) {
			curCost = tmpCost;
			curCell = ( *values.find ( *it ) ).first;
		}
	}
	return curCell;
}

static inline Coords getMaxAndPop ( std::list<Coords> &nodes,const Coords& goal ) {
	std::list<Coords>::iterator max=nodes.begin();
	for ( std::list<Coords>::iterator it=nodes.begin(); it!=nodes.end(); it++ ) {
		if ( !cellCompare ( *max,*it ,goal ) ) {
			max=it;
		}
	}
	Coords ret=*max;
	nodes.erase ( max );
	return ret;
}

Coords CSmartPathFinder::findPath ( Coords  start, Coords  goal,std::function<bool ( const Coords& ) > canStep ) {
	std::list<Coords> nodes;
	std::unordered_set<Coords> marked;
	nodes.push_back ( goal );
	std::unordered_map<Coords, int> values;
	values.insert ( std::make_pair ( goal, 0 ) );
	while ( !nodes.empty() ) {
		Coords currentCoords = getMaxAndPop ( nodes,start );
		if ( currentCoords==start ) {
			break;
		}
		if ( marked.find ( currentCoords ) ==marked.end()  ) {
			int curValue = ( *values.find ( currentCoords ) ).second;
			for ( Coords tmpCoords:getNearCells ( currentCoords ) ) {
				if ( canStep ( tmpCoords ) ) {
					auto it=values.find ( tmpCoords );
					if ( it != values.end() ) {
						if ( it->second >= curValue + 1 ) {
							values.erase ( it );
							values.insert (
							    std::make_pair ( tmpCoords, curValue + 1 ) );
						}
					} else {
						values.insert ( std::make_pair ( tmpCoords, curValue + 1 ) );
					}
					nodes.push_back ( tmpCoords );
				}
			}
			marked.insert ( currentCoords );
		}
	}
	return getNearestCell ( start ,values );
}
