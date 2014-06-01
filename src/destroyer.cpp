#include "destroyer.h"

#include <src/configurationprovider.h>

#include <src/animationprovider.h>

Destroyer Destroyer::instance;

Destroyer::Destroyer() {}

Destroyer::~Destroyer() {
  while (this->size() != 0) {
    delete *this->begin();
  }
  this->clear();
}

void Destroyer::add(AnimatedObject *object) { instance.push_back(object); }

void Destroyer::remove(AnimatedObject *object) {
  instance.std::list<AnimatedObject *>::remove(object);
}
