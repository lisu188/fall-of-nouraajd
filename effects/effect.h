#ifndef EFFECT_H
#define EFFECT_H
#include <string>

class Creature;
class Effect {
  public:
    Effect(int duration);
    virtual ~Effect() = default;
    int getDuration();
    virtual bool apply(Creature *creature);

  protected:
    int dur;

  public:
    std::string className;
};

#endif // EFFECT_H
