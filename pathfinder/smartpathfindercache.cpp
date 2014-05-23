#include "smartpathfinder.h"
#include "smartpathfindercache.h"
#include <QDebug>

void SmartPathFinderCache::addPath(Coords start,Coords end,Coords move){
    mutex.lock();
    cache.insert(std::make_pair(std::make_pair(start,end),move));
    //qDebug() << "Caching: "<<start.x<<start.y<<end.x<<end.y;
    mutex.unlock();
}

Coords SmartPathFinderCache::checkMove(Coords start, Coords stop){
    mutex.lock();
    auto cached=cache.find(std::make_pair(start,stop));
    Coords result;
    if(cached!=cache.end()){
        result= (*cached).second;
    }else{
        result= start;
    }
    mutex.unlock();
    return result;
}

SmartPathFinderCache::SmartPathFinderCache()
{

}

SmartPathFinderCache::SmartPathFinderCache(SmartPathFinderCache &)
{
}

