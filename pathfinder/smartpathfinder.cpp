#include "dumbpathfinder.h"
#include "smartpathfinder.h"
#include <set>
#include <unordered_map>
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
        int level;
        Cell(int x,int y,int z,Coords goal,int level):x(x),y(y),z(z),goal(goal),level(level){}
    };
    class CellCompare{
    public:
        bool operator()(Cell *a,Cell *b){
            int dista=(a->x-a->goal.x)*(a->x-a->goal.x)+(a->y-a->goal.y)*(a->y-a->goal.y);
            int distb=(b->x-b->goal.x)*(b->x-b->goal.x)+(b->y-b->goal.y)*(b->y-b->goal.y);
            if(dista==distb){
                return a<b;
            }
            return dista<distb;
        }
    };
    class FieldQueue :public std::set<Cell*,CellCompare>{
    private:
        std::set<Coords> marked;
        std::unordered_map<Coords,int> prior;
    public:
        void mark(int i,int j){
            marked.insert(Coords(i,j,0));
        }

        void insert(Cell* cell){
            if(marked.find(Coords(cell->x,cell->y,0))!=marked.end()){
                delete cell;
                return;
            }
            if(!((*ConfigurationProvider::getConfig("config/tiles.json"))[GameScene::getGame()->getMap()->getTile(cell->x,cell->y,cell->level)].get("canStep",true).asBool())){
                delete cell;
                return;
            }

        for(FieldQueue::iterator it=begin();it!=end();it++){
            if(((*it)->x==cell->x)&&((*it)->y==cell->y)&&((*it)->z>cell->z)){
                delete (*it);
                erase(it);
                std::set<Cell*,CellCompare>::insert(cell);
                return;
            }
        }
        std::set<Cell*,CellCompare>::insert(cell);
    }
    };

    std::list<Cell*> target;
    FieldQueue queue;
    int level=goal.z;
    Cell *current=new Cell(goal.x,goal.y,0,start,level);
    while(start.x!=current->x||start.y!=current->y){

        queue.insert(new Cell(current->x+1,current->y,current->z+1,start,level));
        queue.insert(new Cell(current->x,current->y+1,current->z+1,start,level));
        queue.insert(new Cell(current->x-1,current->y,current->z+1,start,level));
        queue.insert(new Cell(current->x,current->y-1,current->z+1,start,level));

         queue.mark(current->x,current->y);
         delete current;
         if(queue.empty())break;
         current=*queue.begin();
         queue.erase(queue.begin());
         int dist=std::abs(current->x-start.x)+std::abs(current->y-start.y);
         if(dist==1){
            target.push_front(new Cell(*current));
         }
    }
    if(target.size()==0){
        DumbPathFinder finder;
        return finder.findPath(start,goal);
    }
    int min=target.front()->z;
    int x,y;
    Cell *cellmin=target.front();
    for(std::list<Cell*>::iterator it=target.begin();it!=target.end();it++){
        if((*it)->z<min){
            cellmin=*it;
            min=cellmin->z;
            x=cellmin->x;
            y=cellmin->y;
        }
        delete *it;
    }
    target.clear();
    for(FieldQueue::iterator it=queue.begin();it!=queue.end();it++){
        delete *it;
    }
    queue.clear();
    return Coords(x-start.x,y-y-start.y,0);
}
