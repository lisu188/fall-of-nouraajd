#include "CPathFinder.h"

#ifdef DUMP_PATH
static inline void dump ( std::unordered_map<Coords, int>& values,Coords start,Coords end ) {
    int x=0;
    int y=0;
    double mval=0;
    for ( std::pair<Coords,int> val:values ) {
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
    for ( std::pair<Coords,int> val:values ) {
        int rgb=val.second*scale;
        img.setPixel ( val.first.x,val.first.y,qRgb ( rgb,rgb,rgb ) );
    }
    std::stringstream stream;
    stream<<"dump/dump"<<start.x<<"_"<<start.y<<"_"<<end.x<<"_"<<end.y<<".png";
    img.save ( QString::fromStdString ( stream.str() ),"png" );
}
#else
static inline void dump ( std::unordered_map<Coords, int>& values,Coords start,Coords end ) {
    Q_UNUSED ( values )
    Q_UNUSED ( start )
    Q_UNUSED ( end )
}
#endif

typedef std::function<bool ( const Coords&,const Coords& ) > Compare ;
typedef std::priority_queue<Coords, std::vector<Coords>,Compare> Queue;



Coords CSmartPathFinder::findNextStep ( const Coords &  start, const Coords &  goal, std::function<bool ( const Coords& ) > canStep ) {
    Queue nodes (  [start] ( const Coords& a,const Coords& b ) {
        double dista = ( a.x - start.x ) * ( a.x - start.x ) +
                       ( a.y - start.y ) * ( a.y - start.y ) ;
        double distb = ( b.x - start.x ) * ( b.x - start.x ) +
                       ( b.y - start.y ) * ( b.y - start.y ) ;
        return dista > distb;
    } );
    std::unordered_set<Coords> marked;
    std::unordered_map<Coords, int> values;

    nodes.push ( goal );
    values[goal]=0;

    while ( !nodes.empty() && !contains ( marked,start ) ) {
        Coords currentCoords = nodes.top();
        nodes.pop();
        if (  marked.insert ( currentCoords ).second ) {
            int curValue = values[currentCoords];
            for ( Coords tmpCoords:NEAR ( currentCoords ) ) {
                if ( canStep ( tmpCoords ) ) {
                    auto it=values.find ( tmpCoords );
                    if ( it == values.end() || it->second > curValue + 1 ) {
                        values[tmpCoords] = curValue + 1 ;
                    }
                    nodes.push ( tmpCoords );
                }
            }
        }
    }
    dump ( values,start,goal );
    Coords target=start;
    for ( Coords coords:NEAR ( start ) ) {
        if ( contains ( values,coords ) && ( values[coords]<values[target]|| ( values[coords]==values[target] && coords.getDist ( goal ) <target.getDist ( goal ) ) ) ) {
            target=coords;
        }
    }
    return target;
}
