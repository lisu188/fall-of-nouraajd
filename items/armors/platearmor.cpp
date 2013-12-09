#include "platearmor.h"

PlateArmor::PlateArmor()
{
    className="PlateArmor";
    setAnimation("images/items/armors/platearmor/");
    bonus->setArmor(10);
    bonus->setStamina(3);
    bonus->setStrength(4);
}
