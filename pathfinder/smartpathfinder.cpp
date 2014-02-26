#include "dumbpathfinder.h"
#include "smartpathfinder.h"
#include <deque>
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
        Cell(int x,int y,int z):x(x),y(y),z(z){}
    };
    std::list<Cell*> target;
    std::deque<Cell*> queue;
    int level=goal.z;
    Cell *current=new Cell(goal.x,goal.y,0);
    Map *map=GameScene::getGame()->getMap();
    while(start.x!=current->x||start.y!=current->y){
        std::list<Cell*> list;
        if((*ConfigurationProvider::getConfig("config/tiles.json"))
                     [map->getTile(current->x+1,current->y,level)].get("canStep",true).asBool()){
        list.push_back(new Cell(current->x+1,current->y,current->z+1));}

        if((*ConfigurationProvider::getConfig("config/tiles.json"))
                     [map->getTile(current->x,current->y+1,level)].get("canStep",true).asBool()){
        list.push_back(new Cell(current->x,current->y+1,current->z+1));}

        if((*ConfigurationProvider::getConfig("config/tiles.json"))
                     [map->getTile(current->x-1,current->y,level)].get("canStep",true).asBool()){
        list.push_back(new Cell(current->x-1,current->y,current->z+1));}

        if((*ConfigurationProvider::getConfig("config/tiles.json"))
                     [map->getTile(current->x,current->y-1,level)].get("canStep",true).asBool()){
        list.push_back(new Cell(current->x,current->y-1,current->z+1));}

            for(std::deque<Cell*>::iterator itq=queue.begin();itq!=queue.end();itq++){
                for(std::list<Cell*>::iterator itl=list.begin();itl!=list.end();itl++){
                    Cell *qcell=(*itq);
                    Cell *lcell=(*itl);
                    if(qcell->x==lcell->x&&qcell->y==lcell->y){
                        if(qcell->z>=lcell->z){
                            delete *itq;
                            queue.erase(itq);
                            itq=queue.begin();
                            itl=list.begin();
                        }
                        else{
                            delete *itl;
                            list.erase(itl);
                            itq=queue.begin();
                            itl=list.begin();
                        }
                    }
                }
            }
         for(std::list<Cell*>::iterator itl=list.begin();itl!=list.end();itl++){
            queue.push_front(*itl);
         }
         do{
         delete current;
         current=queue.back();
         queue.pop_back();}
         while(current->z>10&&queue.size()>0);
         if(queue.size()==0)break;
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
