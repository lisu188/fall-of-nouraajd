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
        int x,y;
        Coords goal;
        Cell(int x,int y,Coords goal):x(x),y(y),goal(goal){}
    };
    class CellCompare{
    public:
        bool operator()(const Cell &a,const Cell &b){
            int dista=std::abs(a.x-a.goal.x)+std::abs(a.y-a.goal.y);
            int distb=std::abs(b.x-b.goal.x)+std::abs(b.y-b.goal.y);
            if(dista!=distb)return dista<distb;
            if(a.x!=b.x)return a.x<b.x;
            return a.y<b.y;
        }
    };
    std::set<Cell,CellCompare> nodes;
    std::map<Cell,int,CellCompare> values;

    int level=start.z;
    nodes.insert(Cell(goal.x,goal.y,start));
    values.insert(std::pair<Cell,int>(Cell(goal.x,goal.y,start),0));
    Map *map=GameScene::getGame()->getMap();
    while(!nodes.empty()){
        Cell currentCell=*nodes.begin();
        nodes.erase(nodes.begin());
        bool canStep=(*ConfigurationProvider::getConfig("config/tiles.json"))
                     [map->getTile(currentCell.x,currentCell.y,level)].get("canStep",true).asBool();
        if(!canStep){
            continue;
        }

        int curValue=(*values.find(currentCell)).second;
        for(int i=-1;i<=1;i+=2)
            for(int j=-1;j<=1;j+=2){
        Cell tmpCell(currentCell.x+i,currentCell.y+j,goal);
        if(values.find(tmpCell)!=values.end()){
            int tmpValue=(*values.find(tmpCell)).second;
            if(tmpValue>curValue+1){
                values.erase(values.find(tmpCell));
                nodes.insert(tmpCell);
            }
        }else{
            nodes.insert(tmpCell);
        }
        values.insert(std::pair<Cell,int>(tmpCell,curValue+1));
    }
        std::list<Cell> list;
        for(int i=-1;i<=1;i+=2)
            for(int j=-1;j<=1;j+=2){
                if(values.find(Cell(start.x+i,start.y+j,goal))!=values.end()){
                    list.push_back(Cell(start.x+i,start.y+j,goal));
                }
            }
        if(list.size()==0){
            DumbPathFinder finder;
            return finder.findPath(start,goal);
        }
        int cost=(*values.find(*list.begin())).second;
        Cell target=(*values.find(*list.begin())).first;
        for(std::list<Cell>::iterator it=list.begin();it!=list.end();it++){
            int tmpCost=(*values.find(*it)).second;
            if(tmpCost<cost){
                cost=tmpCost;
                target=(*values.find(*it)).first;
            }
        }
    return Coords(target.x-start.x,target.y-start.y,0);
}
}
