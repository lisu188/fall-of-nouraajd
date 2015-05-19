#include "CPathFinder.h"

#ifdef DUMP_PATH
    #include <QImage>
    #define DUMP_PATH\
    int x=0;\
    int y=0;\
    for(std::pair<Coords,int> val:values){\
        if(val.first.x>x){\
            x=val.first.x;\
        }\
        if(val.first.y>y){\
            y=val.first.y;\
        }\
    }\
    QImage img(QSize(x,y),QImage::Format_Indexed8);\
    for(std::pair<Coords,int> val:values){\
        img.setPixel(val.first.x,val.first.y,val.second);\
    }\
    img.save(QString("dump")+start.x+start.y+goal.x+goal.y);
#else
    #define DUMP_PATH
#endif

typedef std::function<bool ( const Coords&,const Coords& ) > Compare ;
typedef std::priority_queue<Coords, std::vector<Coords>,Compare> Queue;

Coords CSmartPathFinder::findNextStep ( const Coords &  start, const Coords &  goal, std::function<bool ( const Coords& ) > canStep ) {
    Queue nodes (  [goal](const Coords& a,const Coords& b){
        double dista = ( a.x - goal.x ) * ( a.x - goal.x ) +
                      ( a.y - goal.y ) * ( a.y - goal.y ) ;
        double distb = ( b.x - goal.x ) * ( b.x - goal.x ) +
                      ( b.y - goal.y ) * ( b.y - goal.y ) ;
        return dista < distb;
    } );
    std::unordered_set<Coords> marked;
    std::unordered_map<Coords, int> values;

    nodes.push ( goal );
    values[goal]=0;

    while ( !nodes.empty() && !contains(marked,start) ) {
        Coords currentCoords = nodes.top();
        nodes.pop();
        if ( marked.insert ( currentCoords ).second  ) {
            int curValue = values[currentCoords];
            for ( Coords tmpCoords:NEAR ( currentCoords ) ) {
                if ( canStep ( tmpCoords ) ) {
                    auto it=values.find ( tmpCoords );
                    if ( it == values.end()||it->second > curValue + 1 ) {
                        values[tmpCoords] = curValue + 1 ;
                    }
                    nodes.push ( tmpCoords );
                }
            }
        }
    }
    DUMP_PATH
    Coords target=start;
    for(Coords coords:NEAR(start)){
        if(contains(values,coords) && (values[coords]<values[target]||(values[coords]==values[target] && coords.getDist(goal)<target.getDist(goal)))){
            target=coords;
        }
    }
    return target;
}
