#ifndef SMARTPATHFINDERCACHE_H
#define SMARTPATHFINDERCACHE_H
#include <list>
#include <map>
#include <mutex>
#include <map/coords.h>
#include <thread>

class SmartPathFinderCache
{
public:
     static SmartPathFinderCache *getInstance(){
        static SmartPathFinderCache instance;
        return &instance;
    }
    void addPath(Coords start, Coords end, Coords move);
    Coords checkMove(Coords start,Coords stop);


private:
    std::recursive_mutex mutex;
    std::map<std::pair<Coords,Coords>, Coords> cache;
    SmartPathFinderCache();
    SmartPathFinderCache(SmartPathFinderCache &);
};

#endif // SMARTPATHFINDERCACHE_H
