#include <list>

#include <src/animatedobject.h>

#ifndef DESTROYER_H
#define DESTROYER_H

class Destroyer : private std::list<AnimatedObject*>
{
public:
    static void add(AnimatedObject* object);
    static void remove(AnimatedObject* object);
private:
    Destroyer();
    ~Destroyer();
    static Destroyer instance;
};

#endif // DESTROYER_H
