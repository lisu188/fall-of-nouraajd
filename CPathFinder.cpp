#include "CPathFinder.h"
#include "CDefines.h"
#include "templates/hash.h"
#include "templates/util.h"

#define NEAR_COORDS(coords) {\
    Coords(coords.x + 1,coords.y,coords.z),\
    Coords(coords.x - 1,coords.y,coords.z ),\
    Coords(coords.x,coords.y + 1, coords.z ),\
    Coords(coords.x,coords.y - 1,coords.z )}

typedef std::function<bool ( const Coords&,const Coords& ) > Compare ;
typedef std::priority_queue<Coords, std::vector<Coords>,Compare> Queue;
typedef std::shared_ptr<std::unordered_map<Coords, int>> Values;

static force_inline void dump ( Values values,Coords start,Coords end ) {
    int x=0;
    int y=0;
    double mval=0;
    for ( std::pair<Coords,int> val: ( *values ) ) {
        if ( val.first.x>x ) {
            x=val.first.x;
        }
        if ( val.first.y>y ) {
            y=val.first.y;
        }
        if ( val.second>mval ) {
            mval=val.second;
        }
    }
    double scale=256.0/mval;
    QImage img ( QSize ( x+1,y+1 ),QImage::Format_RGB32 );
    img.fill ( 0 );
    for ( std::pair<Coords,int> val: ( *values ) ) {
        int rgb=val.second*scale;
        img.setPixel ( val.first.x,val.first.y,qRgb ( rgb,rgb,rgb ) );
    }
    std::stringstream stream;
    stream<<"dump/dump"<<start.x<<"_"<<start.y<<"_"<<end.x<<"_"<<end.y<<".png";
    img.save ( QString::fromStdString ( stream.str() ),"png" );
}

static force_inline Coords getNextStep ( const Coords& start,  const Coords& goal,Values values ) {
    Coords target=start;
    for ( Coords coords:NEAR_COORDS ( start ) ) {
        if ( vstd::ctn ( ( *values ),coords ) &&
                ( ( *values ) [coords]< ( *values ) [target] ||
                  ( ( *values ) [coords]== ( *values ) [target] &&
                    coords.getDist ( goal ) < target.getDist ( goal ) ) ) ) {
            target=coords;
        }
    }
    return target;
}

static force_inline Values fillValues ( std::function<bool ( const Coords& ) > canStep,
                                        const Coords& goal, const Coords& start ) {
    Queue nodes ( [start] ( const Coords& a,const Coords& b ) {
        double dista = ( a.x - start.x ) * ( a.x - start.x ) +
                       ( a.y - start.y ) * ( a.y - start.y ) ;
        double distb = ( b.x - start.x ) * ( b.x - start.x ) +
                       ( b.y - start.y ) * ( b.y - start.y ) ;
        return dista > distb;
    } );
    std::unordered_set<Coords> marked;
    Values values=std::make_shared<std::unordered_map<Coords, int>>();

    if ( !QApplication::instance()->property ( "disable_pathfinder" ).toBool() ) {
        nodes.push ( goal );
        ( *values ) [goal]=0;

        while ( !nodes.empty() && !vstd::ctn ( marked,start ) ) {
            Coords currentCoords = nodes.top();
            nodes.pop();
            if ( marked.insert ( currentCoords ).second ) {
                int curValue = ( *values ) [currentCoords];
                for ( Coords tmpCoords:NEAR_COORDS ( currentCoords ) ) {
                    if ( canStep ( tmpCoords ) ) {
                        auto it=values->find ( tmpCoords );
                        if ( it == values->end() || it->second > curValue + 1 ) {
                            ( *values ) [tmpCoords] = curValue + 1 ;
                        }
                        nodes.push ( tmpCoords );
                    }
                }
            }
        }
        if ( QApplication::instance()->property ( "dump_path" ).toBool() ) {
            dump ( values,start,goal );
        }
    }
    return values;
}

Coords CSmartPathFinder::findNextStep ( const Coords & start, const Coords & goal, std::function<bool ( const Coords& ) > canStep ) {
    return getNextStep ( start,goal,fillValues ( canStep, goal, start ) );
}

std::list<Coords> CSmartPathFinder::findPath ( const Coords &start, const Coords &goal, std::function<bool ( const Coords & ) > canStep ) {
    std::list<Coords> path;
    Values val=fillValues ( canStep,start,goal );
    Coords next=getNextStep ( next,goal,val );
    if ( next!=start ) {
        while ( next!=goal ) {
            next=getNextStep ( next,goal,val );
            path.push_front ( next );
        }
    }
    return path;
}
