#include "effect.h"
#include <QDebug>
#include <creatures/creature.h>

Effect::Effect(int duration):dur(duration)
{
    className="Effect";
}

int Effect::getDuration() {
    return dur;
}

bool Effect::apply(Creature *creature)
{
    dur--;
    if(dur==0)
    {
        qDebug()<<className.c_str()<<"ends for"<<creature->className.c_str();
        return false;
    }
}
