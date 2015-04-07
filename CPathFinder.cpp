#include "CPathFinder.h"
#include"CMap.h"
#include "object/CObject.h"

#include <unordered_map>
#include <unordered_set>

#include <queue>

#include <functional>

typedef std::function<int ( const Coords&,const Coords& ) > Compare ;
typedef std::priority_queue<Coords, std::vector<Coords>,Compare> Queue;

static  inline int cellCompare ( const Coords &a, const Coords &b , const Coords &goal ) {
	float dista = ( a.x - goal.x ) * ( a.x - goal.x ) +
	              ( a.y - goal.y ) * ( a.y - goal.y ) ;
	float distb = ( b.x - goal.x ) * ( b.x - goal.x ) +
	              ( b.y - goal.y ) * ( b.y - goal.y ) ;
	return dista - distb;
}

static inline  std::list<Coords> getNearCells ( const Coords & coords ) {
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

static inline Coords getNearestCell ( const Coords & start ,const Coords &goal,std::unordered_map<Coords, int> &values ) {
	Compare cmp=[&values,&goal] ( const Coords &a,const Coords &b ) {
		auto it1=values.find ( a );
		auto it2=values.find ( b );
		if ( it1==values.end() &&it2==values.end() ) {
			return 0;
		}
		if ( it1==values.end() ) {
			return -1;
		}
		if ( it2==values.end() ) {
			return 1;
		}
		int cmp= ( *it1 ).second- ( *it2 ).second;
		if ( cmp ) {
			return cmp;
		}
		return cellCompare ( a,b,goal );
	};
	auto l=getNearCells ( start ) ;
	Queue queue ( l.begin(),l.end(),cmp );
	return queue.top();
}

Coords CSmartPathFinder::findPath ( const Coords &  start, const Coords &  goal, std::function<bool ( const Coords& ) > canStep ) {
	Queue nodes (  std::bind ( cellCompare,std::placeholders::_1,std::placeholders::_2,start ) );
	std::unordered_set<Coords> marked;
	nodes.push ( goal );
	std::unordered_map<Coords, int> values;
	values.insert ( std::make_pair ( goal, 0 ) );
	while ( !nodes.empty() &&! ( nodes.top() ==start ) ) {
		Coords currentCoords = nodes.top();
		nodes.pop();
		if ( marked.find ( currentCoords ) == marked.end()  ) {
			marked.insert ( currentCoords );
			int curValue = ( *values.find ( currentCoords ) ).second;
			for ( Coords tmpCoords:getNearCells ( currentCoords ) ) {
				if ( canStep ( tmpCoords ) ) {
					auto it=values.find ( tmpCoords );
					if ( it == values.end() ) {
						values.insert ( std:: make_pair ( tmpCoords, curValue + 1 ) );
					} else if ( it->second >= curValue + 1 ) {
						values.erase ( it );
						values.insert (
						    std::make_pair ( tmpCoords, curValue + 1 ) );
					}
					nodes.push ( tmpCoords );
				}
			}
		}
	}
	return getNearestCell ( start ,goal,values );
}
