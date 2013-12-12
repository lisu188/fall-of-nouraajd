#include "lifepotioneffect.h"
#include "manapotioneffect.h"
#include "potioneffect.h"
#include <string>

PotionEffect::PotionEffect()
{
}

PotionEffect *PotionEffect::getPotionEffect(const char *name)
{
    std::string type=name;
    if((type.find("LifePotion") != std::string::npos))
    {
        return new LifePotionEffect();
    } else if(type.find("ManaPotion") != std::string::npos) {
        return new ManaPotionEffect();
    }
    else
    {
        std::exception e;
        throw e;
    }
}
