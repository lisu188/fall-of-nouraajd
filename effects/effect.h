#ifndef EFFECT_H
#define EFFECT_H
#include <string>
#include <unordered_map>
#include <functional>
class Creature;
class Stats;

class Effect
{
public:
    Effect(std::string type, Creature *caster, int duration);
    int getTimeLeft();
    int getTimeTotal();
    Creature *getCaster();
    bool apply(Creature *creature);
    std::string className;
    Stats *getBonus();
    void setBonus(Stats *value);

private:
    std::function<bool (Effect *effect, Creature *)> effect;
    static std::unordered_map<std::string,std::function<bool (Effect *effect, Creature *)>> effects;

    int timeLeft;
    int timeTotal;
    Stats *bonus;
    Creature *caster;

};
bool Stun(Effect *effect, Creature *creature);
bool EndlessPainEffect(Effect *effect, Creature *creature);
bool AbyssalShadowsEffect(Effect *effect, Creature *creature);
bool ArmorOfEndlessWinterEffect(Effect *effect,Creature *creature);

#endif // EFFECT_H
