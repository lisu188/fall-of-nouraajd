#include <list>

#include <animation/animatedobject.h>

#ifndef DESTROYER_H
#define DESTROYER_H

class Destroyer : private std::list<AnimatedObject*>
{
public:
    static void add(AnimatedObject* object);
    static void remove(AnimatedObject* object);
    static void terminate();
private:
    Destroyer();
    ~Destroyer();
    static Destroyer *instance;

};

#endif // DESTROYER_H
