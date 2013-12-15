#include "effect.h"
#include <QDebug>
#include <creatures/creature.h>

std::unordered_map<std::string,std::function<bool (Effect *effects, Creature *)>> Effect::effects
{
    {"Stun",&Stun},{"EndlessPainEffect",&EndlessPainEffect},
    {"AbyssalShadowsEffect",&AbyssalShadowsEffect},{"ArmorOfEndlessWinterEffect",&ArmorOfEndlessWinterEffect}
};

Effect::Effect(std::string type,Creature *caster, int duration):caster(caster)
{
    bonus=0;
    className=type;
    timeLeft=timeTotal=duration;
    effect=effects[type];
}

int Effect::getTimeLeft() {
    return timeLeft;
}

int Effect::getTimeTotal() {
    return timeTotal;
}

Creature *Effect::getCaster() {
    return caster;
}

bool Effect::apply(Creature *creature)
{
    if(bonus)if(timeTotal==timeLeft) {
            creature->getStats()->addBonus(*bonus);
        }
    timeLeft--;
    if(timeLeft==0)
    {
        if(bonus) {
            creature->getStats()->removeBonus(*bonus);
        }
        return false;
    }
    return effect(this,creature);
}

Stats *Effect::getBonus()
{
    return bonus;
}

void Effect::setBonus(Stats *value)
{
    bonus = value;
}



bool Stun(Effect *effect, Creature *creature)
{
    return true;
}


bool EndlessPainEffect(Effect *effect, Creature *creature)
{
    creature->hurt(effect->getCaster()->getDmg()*15.0/100.0);
    return true;
}


bool AbyssalShadowsEffect(Effect *effect, Creature *creature)
{
    if(effect->getTimeLeft()>1)
    {
        Damage tmp;
        tmp.setShadow(effect->getCaster()->getDmg()*45.0/100.0);
        creature->hurt(tmp);
    }
    else
    {
        Damage tmp;
        tmp.setShadow(effect->getCaster()->getDmg());
        creature->hurt(tmp);
    }
    return false;
}

bool ArmorOfEndlessWinterEffect(Effect *effect,Creature *creature)
{
    creature->healProc(20);
    return false;//must implement ban to other skills
}
