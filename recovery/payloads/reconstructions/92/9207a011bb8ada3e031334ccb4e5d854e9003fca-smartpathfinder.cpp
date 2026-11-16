#include "dumbpathfinder.h"
#include "smartpathfinder.h"
#include "smartpathfindercache.h"
#include <QDebug>
#include <view/gamescene.h>
#include <configuration/configurationprovider.h>
#include <math.h>

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
    Coords next=SmartPathFinderCache::getInstance()->checkMove(start,goal);
    if(next==start){
        values.clear();
        std::list<Cell> nodes;
        std::unordered_set<Coords,CoordsHasher> marked;
        nodes.push_back(Cell(goal.x,goal.y,start));
        values.insert(std::make_pair(Coords(goal.x,goal.y,start.z),0));
        while(!nodes.empty()&&marked.find(start)==marked.end()){
            processNode(start,nodes,marked);
        }
        next=getNearestCell(start);
        if(next==start){
            DumbPathFinder finder;
            return finder.findPath(start,goal);
        }
        SmartPathFinderCache::getInstance()->addPath(start,goal,next);
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

bool SmartPathFinder::canStep(int x, int y, int z)
{
    Map *map=GameScene::getGame()->getMap();
    return (*ConfigurationProvider::getConfig("config/tiles.json"))
            [map->getTile(x,y,z)].get("canStep",true).asBool();
}
