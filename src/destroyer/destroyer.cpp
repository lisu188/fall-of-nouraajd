#include "destroyer.h"

#include <src/configuration/configurationprovider.h>

#include <src/animation/animationprovider.h>

Destroyer *Destroyer::instance = 0;

Destroyer::Destroyer()
{
}

Destroyer::~Destroyer()
{
    while (this->size() != 0) {
        delete *this->begin();
    }
    this->clear();
    AnimationProvider::terminate();
    ConfigurationProvider::terminate();
}

void Destroyer::add(AnimatedObject *object)
{
    if (!instance) {
        instance = new Destroyer();
    }
    instance->push_back(object);
}

void Destroyer::remove(AnimatedObject *object)
{
    instance->std::list<AnimatedObject*>::remove(object);
}

void Destroyer::terminate()
{
    delete instance;
}
