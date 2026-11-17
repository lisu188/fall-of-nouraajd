#include "pathfinder.h"
#include <QDebug>
#include <src/gamescene.h>
#include <src/configurationprovider.h>
#include <math.h>

PathFinder::PathFinder()
{
}

// ---- formerly dumbpathfinder.cpp ----
DumbPathFinder::DumbPathFinder()
{

}

DumbPathFinder::DumbPathFinder(const DumbPathFinder&)
{
}

Coords DumbPathFinder::findPath(Coords start, Coords goal)
{
    int px=goal.x;
    int py=goal.y;
    int dirx=px-start.x;
    int diry=py-start.y;
    int movx,movy;
    if(dirx>0) {
        movx=1;
    }
    else if(dirx==0) {
        movx=0;
    }
    else {
        movx=-1;
    }
    if(diry>0) {
        movy=1;
    }
    else if(diry==0) {
        movy=0;
    }
    else {
        movy=-1;
    }
    if(movx!=0&&movy!=0)
    {
        switch(rand()%2)
        {
        case 0:
            movx=0;
            break;
        case 1:
            movy=0;
            break;
        }
    }
    return Coords(movx,movy,0);
}

// ---- formerly randompathfinder.cpp ----
RandomPathFinder::RandomPathFinder()
{

}

RandomPathFinder::RandomPathFinder(const RandomPathFinder &)
{
}

Coords RandomPathFinder::findPath(Coords , Coords)
{
    int a=rand()%3-1;
    int b=rand()%3-1;
    return Coords(a,b,0);
}

// ---- formerly smartpathfinder.cpp ----
SmartPathFinder::SmartPathFinder()
{
}

SmartPathFinder::SmartPathFinder(const SmartPathFinder &)
{

}

Coords SmartPathFinder::findPath(Coords start, Coords goal)
{
    if(start.z!=goal.z){
        qDebug()<<"Changing Level Not Supported Yet.";
        throw new std::exception();
    }
    values.clear();
    std::list<Cell> nodes;
    std::unordered_set<Coords,CoordsHasher> marked;
    nodes.push_back(Cell(goal.x,goal.y,start));
    values.insert(std::make_pair(Coords(goal.x,goal.y,start.z),0));
    while(!nodes.empty()&&marked.find(start)==marked.end()){
        processNode(start,nodes,marked);
    }
    Coords next=getNearestCell(start);
    if(next==start){
        DumbPathFinder finder;
        return finder.findPath(start,goal);
    }
    return Coords(next.x-start.x,next.y-start.y,0);
}

int SmartPathFinder::getCost(Coords coords)
{
    std::unordered_map<Coords,int,CoordsHasher>::iterator it=values.find(coords);
    if(it==values.end()){
        return -1;
    }
    return (*it).second;
}

std::list<Coords> SmartPathFinder::getNearCells(Coords coords)
{
    std::list<Coords> list;
    for(int i=-1;i<=1;i++)
        for(int j=-1;j<=1;j++){
            if(i!=0&&j!=0)continue;
            if(i==0&&j==0)continue;
            list.push_back(Coords(coords.x+i,coords.y+j,coords.z));
        }
    return list;
}

Coords SmartPathFinder::getNearestCell(Coords start)
{
    Coords target=start;
    int cost=-1;
    std::list<Coords> list=getNearCells(start);
    for(std::list<Coords>::iterator it=list.begin();it!=list.end();it++){
        int tmpCost=getCost(*it);
        if(tmpCost>=0&&(cost<0||tmpCost<cost)){
            cost=tmpCost;
            target=*it;
        }
    }
    return target;
}

void SmartPathFinder::processNode(Coords start, std::list<Cell> &nodes, std::unordered_set<Coords,CoordsHasher> &marked)
{
    std::list<Cell>::iterator nearest=nodes.begin();
    int nearestDist=-1;
    for(std::list<Cell>::iterator it=nodes.begin();it!=nodes.end();it++){
        int dist=sqrt((it->x-start.x)*(it->x-start.x)+(it->y-start.y)*(it->y-start.y));
        if(nearestDist<0||dist<nearestDist){
            nearestDist=dist;
            nearest=it;
        }
    }
    Cell currentCell=*nearest;
    nodes.erase(nearest);
    Coords current=currentCell.toCoords();
    if(marked.find(current)!=marked.end()){
        return;
    }
    marked.insert(current);
    if(current==start){
        return;
    }
    int curValue=getCost(current);
    std::list<Coords> near=getNearCells(current);
    for(std::list<Coords>::iterator it=near.begin();it!=near.end();it++){
        Coords tmp=*it;
        if(!canStep(tmp.x,tmp.y,tmp.z)){
            continue;
        }
        int tmpValue=getCost(tmp);
        if(tmpValue<0||tmpValue>=curValue+1){
            values[tmp]=curValue+1;
        }
        nodes.push_back(Cell(tmp.x,tmp.y,start));
    }
}

// The map of the creature whose path is being searched, recorded on the main thread.
static Map *pathMap = 0;

bool SmartPathFinder::canStep(int x, int y, int z)
{
    Map *map=pathMap;
    return (*ConfigurationProvider::getConfig("config/tiles.json"))
            [map->getTile(x,y,z)].get("canStep",true).asBool();
}

// ---- worker added by this commit: paths are found on the thread pool ----
PathFinderWorker::PathFinderWorker(Creature *creature, PathFinder *finder)
    : creature(creature), finder(finder)
{
    pathMap = creature->getMap();
    setAutoDelete(true);
    connect(this, SIGNAL(completed(int,int)), creature, SLOT(move(int,int)), Qt::QueuedConnection);
    connect(this, SIGNAL(started()), CompletionListener::getInstance(), SLOT(registerWorker()));
    connect(this, SIGNAL(ended()), CompletionListener::getInstance(), SLOT(deregisterWorker()), Qt::QueuedConnection);
    Q_EMIT started();
}

void PathFinderWorker::run()
{
    Player *player = dynamic_cast<GameScene *>(creature->getMap()->getScene())->getPlayer();
    Coords path = finder->findPath(creature->getCoords(), player->getCoords());
    delete finder;
    Q_EMIT completed(path.x, path.y);
    Q_EMIT ended();
}

// ---- added by this commit: counts running path searches for the current move ----
void CompletionListener::run()
{
    if (started && workers == 0) {
        Q_EMIT completed();
    }
}

void CompletionListener::registerWorker()
{
    workers++;
}

void CompletionListener::deregisterWorker()
{
    workers--;
    if (started && workers == 0) {
        Q_EMIT completed();
    }
}
