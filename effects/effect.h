#ifndef EFFECT_H
#define EFFECT_H
class Creature;
class Effect
{
public:
    Effect(int duration);
    virtual void apply(Creature *creature)=0;
private:
    int dur;
};

#endif // EFFECT_H
