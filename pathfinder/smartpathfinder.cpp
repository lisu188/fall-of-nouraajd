#include "dumbpathfinder.h"
#include "smartpathfinder.h"
#include <queue>
#include <QDebug>
#include <view/gamescene.h>
#include <configuration/configurationprovider.h>
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
    class Cell{
    public:
        int x,y,z;
        Coords goal;
        Cell(int x,int y,int z,Coords goal):x(x),y(y),z(z),goal(goal){}
    };
    class CellCompare{
    public:
        bool operator()(Cell *a,Cell *b){
            int dista=std::abs(a->x-a->goal.x)+std::abs(a->y-a->goal.y);
            int distb=std::abs(b->x-b->goal.x)+std::abs(b->y-b->goal.y);
            return dista>distb;
        }
    };

    std::list<Cell*> target;
    std::priority_queue<Cell*,std::deque<Cell*>,CellCompare> queue;
    int level=goal.z;
    Cell *current=new Cell(goal.x,goal.y,0,start);
    Map *map=GameScene::getGame()->getMap();
    while(start.x!=current->x||start.y!=current->y){
        if((*ConfigurationProvider::getConfig("config/tiles.json"))
                     [map->getTile(current->x,current->y,level)].get("canStep",true).asBool()){
        queue.push(new Cell(current->x+1,current->y,current->z+1,start));
        queue.push(new Cell(current->x,current->y+1,current->z+1,start));
        queue.push(new Cell(current->x-1,current->y,current->z+1,start));
        queue.push(new Cell(current->x,current->y-1,current->z+1,start));
}
         delete current;
         current=queue.top();
         queue.pop();
         if(queue.empty())break;
         int dist=std::abs(current->x-start.x)+std::abs(current->y-start.y);
         if(dist==1){
            target.push_front(current);
         }
    }
    if(target.size()==0){
        DumbPathFinder finder;
        return finder.findPath(start,goal);
    }
    int min=target.front()->z;
    Cell *cellmin=target.front();
    for(std::list<Cell*>::iterator it=target.begin();it!=target.end();it++){
        if((*it)->z<min){
            cellmin=*it;
            min=cellmin->z;
        }
    }
    return Coords(cellmin->x-start.x,cellmin->y-start.y,0);
}
