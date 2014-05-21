#include "randompathfinder.h"

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


